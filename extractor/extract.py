"""Lane 1 extractor: yfinance (Tiingo fallback) -> GCS landing zone -> BigQuery raw.prices_raw.
Follows docs/schema_contract.md v0.2 (PR #25)."""
import argparse
import io
import os
from datetime import date, timedelta

import pandas as pd
import requests
import yfinance as yf
from google.cloud import bigquery, storage

PROJECT = "market-bubble-alert"
BUCKET = "market-bubble-alert-landing"
TABLE = f"{PROJECT}.raw.prices_raw"

# From dbt/seeds/basket_members.csv. TODO: read from basket_members once Lane 2 seeds it.
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


def fetch_yfinance(start, end):
    """Returns {ticker: DataFrame}; tickers yfinance failed on are simply absent."""
    try:
        raw = yf.download(TICKERS, start=start, end=end + timedelta(days=1),
                          auto_adjust=False, group_by="ticker", progress=False)
    except Exception as e:
        print(f"WARN yfinance failed entirely: {e}")
        return {}
    if raw is None or raw.empty:
        return {}
    out = {}
    for t in TICKERS:
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


def fetch(start, end, run_id, force_fallback=False):
    got = {} if force_fallback else fetch_yfinance(start, end)
    for t in TICKERS:
        if t in got:
            continue
        print(f"WARN yfinance had no rows for {t}, trying Tiingo")
        fb = fetch_tiingo(t, start, end)
        if fb is None:
            print(f"ERROR no source served {t}")
            continue
        got[t] = fb
    if not got:
        raise SystemExit("No data returned for any ticker")
    df = pd.concat([g.assign(ticker=t) for t, g in got.items()], ignore_index=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"], utc=True).dt.date
    df["volume"] = pd.to_numeric(df["volume"]).round().astype("Int64")
    df.loc[df["ticker"].str.startswith("^"), "volume"] = pd.NA  # NULL for indexes
    df["ingested_at"] = pd.Timestamp.now(tz="UTC").floor("s")
    df["run_id"] = pd.Series([run_id] * len(df), dtype="string", index=df.index)
    print("Rows by source:", df.groupby("source")["ticker"].nunique().to_dict(), "tickers")
    return df[COLS]


def to_gcs(df, credentials=None):
    """One parquet per trading day; re-running a date overwrites its file."""
    bucket = storage.Client(project=PROJECT, credentials=credentials).bucket(BUCKET)
    uris = []
    for d, g in df.groupby("trade_date"):
        path = f"prices/trade_date={d}/prices.parquet"
        buf = io.BytesIO()
        g.to_parquet(buf, index=False, coerce_timestamps="us")
        bucket.blob(path).upload_from_string(buf.getvalue())
        uris.append(f"gs://{BUCKET}/{path}")
    return uris


def to_bigquery(uris, dates, credentials=None):
    """Delete the dates being loaded, then append, so reruns never duplicate."""
    bq = bigquery.Client(project=PROJECT, credentials=credentials)
    table = bigquery.Table(TABLE, schema=SCHEMA)
    table.time_partitioning = bigquery.TimePartitioning(field="trade_date")
    table.clustering_fields = ["ticker"]
    bq.create_table(table, exists_ok=True)
    bq.query(
        f"DELETE FROM `{TABLE}` WHERE trade_date IN UNNEST(@dates)",
        job_config=bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("dates", "DATE", dates)]),
    ).result()
    bq.load_table_from_uri(uris, TABLE, job_config=bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        write_disposition="WRITE_APPEND")).result()
    n = list(bq.query(f"SELECT COUNT(*) FROM `{TABLE}`").result())[0][0]
    print(f"raw.prices_raw now has {n} rows")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--start", type=date.fromisoformat,
                   default=date.today() - timedelta(days=7))
    p.add_argument("--end", type=date.fromisoformat, default=date.today())
    p.add_argument("--run-id", default=None)
    p.add_argument("--force-fallback", action="store_true",
                   help="Skip yfinance and use Tiingo, to test or demo the fallback")
    p.add_argument("--dry-run", action="store_true", help="Fetch only; write nothing")
    a = p.parse_args()
    df = fetch(a.start, a.end, a.run_id, a.force_fallback)
    print(f"Fetched {len(df)} rows, {df['ticker'].nunique()} tickers, "
          f"{df['trade_date'].nunique()} dates")
    if a.dry_run:
        print(df.head(3).to_string())
    else:
        uris = to_gcs(df)
        to_bigquery(uris, sorted(df["trade_date"].unique()))
