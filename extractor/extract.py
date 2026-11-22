"""Lane 1 extractor: yfinance (Tiingo fallback) -> GCS landing zone -> BigQuery raw.prices_raw.
Follows docs/schema_contract.md v0.2 (PR #25) and the v0.3 addendum, section 1 item 1:
the tracked symbols are the union of basket_members and universe_members (#69)."""
import argparse
import hashlib
import io
import os
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from google.api_core.exceptions import NotFound
from google.cloud import bigquery, storage

PROJECT = "market-bubble-alert"
BUCKET = "market-bubble-alert-landing"
TABLE = f"{PROJECT}.raw.prices_raw"
MEMBERS_DATASET = "marts"  # dbt seeds land in `marts` on the prod target
YF_CHUNK = 50              # tickers per yfinance call; smaller batches fail less often
TIINGO_MAX = 40            # free tier allows 50 requests/hour; leave headroom for retries

# Phase 1 roster, used only if basket_members can't be read, so the daily run never loses
# the official 24. The live list comes from the tables (load_tickers).
TICKERS = [
    "CRWV", "NBIS", "IREN", "APLD", "WULF", "CIFR", "SMCI", "AI", "SOUN", "BBAI", "SPCX",
    "MSFT", "GOOGL", "META", "AMZN", "NVDA", "AVGO", "ORCL",
    "^GSPC",
    "ARKK", "HYG", "IEF", "SPY", "RSP",
]

PRICE_COLS = ["trade_date", "open", "high", "low", "close", "adj_close", "volume", "source"]
COLS = ["trade_date", "ticker", "open", "high", "low", "close",
        "adj_close", "volume", "source", "ingested_at", "run_id"]
SCHEMA = [
    bigquery.SchemaField("trade_date", "DATE"),
    bigquery.SchemaField("ticker", "STRING"),
    bigquery.SchemaField("open", "FLOAT64"),
    bigquery.SchemaField("high", "FLOAT64"),
    bigquery.SchemaField("low", "FLOAT64"),
    bigquery.SchemaField("close", "FLOAT64"),
    bigquery.SchemaField("adj_close", "FLOAT64"),
    bigquery.SchemaField("volume", "INT64"),
    bigquery.SchemaField("source", "STRING"),
    bigquery.SchemaField("ingested_at", "TIMESTAMP"),
    bigquery.SchemaField("run_id", "STRING"),
]

# A span is "in force" during [start, end] if it began on or before end and had not ended by start.
MEMBERS_SQL = """
SELECT DISTINCT UPPER(ticker) AS ticker
FROM `{table}`
WHERE added_date <= @end
  AND (removed_date IS NULL OR removed_date > @start)
"""


def _members(bq, table, start, end):
    job = bq.query(MEMBERS_SQL.format(table=table), job_config=bigquery.QueryJobConfig(
        query_parameters=[bigquery.ScalarQueryParameter("start", "DATE", start),
                          bigquery.ScalarQueryParameter("end", "DATE", end)]))
    return [r.ticker for r in job.result()]


def combine(basket, universe):
    """Union of the two lists, basket first, duplicates dropped (NVDA can be in both)."""
    seen, out = set(), []
    for t in list(basket) + list(universe):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def load_tickers(start, end, credentials=None, dataset=MEMBERS_DATASET):
    """Tracked symbols for [start, end]: basket_members plus universe_members.

    - basket_members unreadable: fall back to the hard-coded Phase 1 list, so the official
      dial keeps getting prices.
    - universe_members missing (not seeded yet): load the basket only, with a warning.
    """
    bq = bigquery.Client(project=PROJECT, credentials=credentials)
    try:
        basket = _members(bq, f"{PROJECT}.{dataset}.basket_members", start, end)
    except Exception as e:
        print(f"WARN could not read {dataset}.basket_members ({e}); using the Phase 1 list")
        basket = list(TICKERS)
    try:
        universe = _members(bq, f"{PROJECT}.{dataset}.universe_members", start, end)
    except NotFound:
        print(f"WARN {dataset}.universe_members not found; loading basket_members only")
        universe = []
    tickers = combine(basket, universe)
    print(f"Tickers: {len(basket)} basket + {len(universe)} universe "
          f"- {len(basket) + len(universe) - len(tickers)} in both = {len(tickers)}")
    return tickers


def fetch_yfinance(tickers, start, end):
    """Returns {ticker: DataFrame}; tickers yfinance failed on are simply absent."""
    out = {}
    for i in range(0, len(tickers), YF_CHUNK):
        chunk = tickers[i:i + YF_CHUNK]
        try:
            raw = yf.download(chunk, start=start, end=end + timedelta(days=1),
                              auto_adjust=False, group_by="ticker", progress=False,
                              threads=True)
        except Exception as e:
            print(f"WARN yfinance failed on chunk {i // YF_CHUNK + 1}: {e}")
            continue
        if raw is None or raw.empty:
            continue
        for t in chunk:
            if t not in raw.columns.get_level_values(0):
                continue
            sub = raw[t].dropna(subset=["Close", "Adj Close"]).reset_index()
            if sub.empty:
                continue
            sub = sub.rename(columns={
                "Date": "trade_date", "Open": "open", "High": "high", "Low": "low",
                "Close": "close", "Adj Close": "adj_close", "Volume": "volume"})
            sub["source"] = "yfinance"
            out[t] = sub[PRICE_COLS]
    return out


def fetch_tiingo(ticker, start, end):
    """Fallback for one ticker. Tiingo serves stocks and ETFs, not index levels like ^GSPC."""
    key = os.environ.get("TIINGO_API_KEY")
    if not key:
        print("WARN TIINGO_API_KEY not set, no fallback available")
        return None
    if ticker.startswith("^"):
        return None
    r = requests.get(f"https://api.tiingo.com/tiingo/daily/{ticker}/prices",
                     params={"startDate": str(start), "endDate": str(end), "token": key},
                     timeout=30)
    if r.status_code != 200 or not r.json():
        print(f"WARN Tiingo returned {r.status_code} for {ticker}")
        return None
    df = pd.DataFrame(r.json()).rename(columns={"date": "trade_date", "adjClose": "adj_close"})
    df["source"] = "tiingo"
    return df[PRICE_COLS]


def fetch(start, end, run_id, force_fallback=False, tickers=None):
    tickers = list(tickers) if tickers else list(TICKERS)
    got = {} if force_fallback else fetch_yfinance(tickers, start, end)
    missing = [t for t in tickers if t not in got]
    if len(missing) > TIINGO_MAX:
        print(f"WARN {len(missing)} tickers missing from yfinance; Tiingo tries the first "
              f"{TIINGO_MAX} only (free tier is 50 requests/hour)")
    for t in missing[:TIINGO_MAX]:
        print(f"WARN yfinance had no rows for {t}, trying Tiingo")
        fb = fetch_tiingo(t, start, end)
        if fb is not None:
            got[t] = fb
    failed = [t for t in tickers if t not in got]
    if failed:
        print(f"ERROR no source served {len(failed)} tickers: {', '.join(failed)}")
    if not got:
        raise SystemExit("No data returned for any ticker")
    df = pd.concat([g.assign(ticker=t) for t, g in got.items()], ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"], utc=True).dt.date
    df["volume"] = pd.to_numeric(df["volume"]).round().astype("Int64")
    df.loc[df["ticker"].str.startswith("^"), "volume"] = pd.NA  # NULL for indexes
    df["ingested_at"] = pd.Timestamp.now(tz="UTC").floor("s")
    df["run_id"] = pd.Series([run_id] * len(df), dtype="string", index=df.index)
    print("Tickers by source:", df.groupby("source")["ticker"].nunique().to_dict())
    return df[COLS]


def group_name(tickers):
    """Stable file name for a set of tickers. The same set always overwrites its own file;
    a different set (one new ticker, a test) gets its own file and can't overwrite this one."""
    key = ",".join(sorted(set(tickers)))
    return "prices_" + hashlib.sha1(key.encode()).hexdigest()[:10]


def to_gcs(df, credentials=None, prefix="prices"):
    """One parquet per trading day per ticker set; re-running the same set overwrites its file."""
    bucket = storage.Client(project=PROJECT, credentials=credentials).bucket(BUCKET)
    name = group_name(df["ticker"].unique())
    uris = []
    for d, g in df.groupby("trade_date"):
        path = f"{prefix}/trade_date={d}/{name}.parquet"
        buf = io.BytesIO()
        g.to_parquet(buf, index=False, coerce_timestamps="us")
        bucket.blob(path).upload_from_string(buf.getvalue())
        uris.append(f"gs://{BUCKET}/{path}")
    return uris


def to_bigquery(uris, dates, tickers, credentials=None, table_id=TABLE):
    """Delete only the (date, ticker) pairs being loaded, then append, so reruns never
    duplicate and a partial load (one ticker, a test) never removes anyone else's rows."""
    bq = bigquery.Client(project=PROJECT, credentials=credentials)
    table = bigquery.Table(table_id, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(field="trade_date")
    table.clustering_fields = ["ticker"]
    bq.create_table(table, exists_ok=True)
    bq.query(
        f"DELETE FROM `{table_id}` WHERE trade_date IN UNNEST(@dates) AND ticker IN UNNEST(@tickers)",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates),
            bigquery.ArrayQueryParameter("tickers", "STRING", sorted(set(tickers)))]),
    ).result()
    for i in range(0, len(uris), 5000):  # a load job takes up to 10,000 URIs
        bq.load_table_from_uri(uris[i:i + 5000], table_id, job_config=bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            write_disposition="WRITE_APPEND")).result()
    n = list(bq.query(f"SELECT COUNT(*) FROM `{table_id}`").result())[0][0]
    print(f"{table_id} now has {n} rows")


def load(df, credentials=None, table_id=TABLE, prefix="prices"):
    """GCS then BigQuery for one fetched frame."""
    uris = to_gcs(df, credentials=credentials, prefix=prefix)
    to_bigquery(uris, sorted(df["trade_date"].unique()), df["ticker"].unique().tolist(),
                credentials=credentials, table_id=table_id)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat,
                   default=date.today() - timedelta(days=7))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--run-id", default=None)
    p.add_argument("--tickers", default=None,
                   help="Comma-separated list, e.g. PLTR or PLTR,AMD; skips the member tables")
    p.add_argument("--members-dataset", default=MEMBERS_DATASET,
                   help="Dataset holding basket_members and universe_members (default: marts)")
    p.add_argument("--table", default=TABLE, help="Target table (default: raw.prices_raw)")
    p.add_argument("--gcs-prefix", default="prices", help="Landing folder in the bucket")
    p.add_argument("--force-fallback", action="store_true",
                   help="Skip yfinance and use Tiingo, to test or demo the fallback")
    p.add_argument("--dry-run", action="store_true", help="Fetch only; write nothing")
    a = p.parse_args()
    if a.tickers:
        tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
    else:
        tickers = load_tickers(a.start, a.end, dataset=a.members_dataset)
    df = fetch(a.start, a.end, a.run_id, a.force_fallback, tickers=tickers)
    print(f"Fetched {len(df)} rows, {df['ticker'].nunique()} tickers, "
          f"{df['trade_date'].nunique()} dates")
    if a.dry_run:
        print(df.head(3).to_string())
    else:
        load(df, table_id=a.table, prefix=a.gcs_prefix)
