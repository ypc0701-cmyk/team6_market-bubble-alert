"""Lane 1 extractor: yfinance -> GCS landing zone -> BigQuery raw.prices_raw.
Follows docs/schema_contract.md v0.2 (PR #25)."""
import argparse
import io
from datetime import date, timedelta

import pandas as pd
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


def fetch(start, end, run_id):
    raw = yf.download(TICKERS, start=start, end=end + timedelta(days=1),
                      auto_adjust=False, group_by="ticker", progress=False)
    frames = []
    for t in TICKERS:
        if t not in raw.columns.get_level_values(0):
            print(f"WARN no data returned for {t}")
            continue
        sub = raw[t].dropna(subset=["Close", "Adj Close"]).reset_index()
        if sub.empty:
            print(f"WARN no rows for {t}")
            continue
        sub["ticker"] = t
        frames.append(sub)
    if not frames:
        raise SystemExit("No data returned for any ticker")
    df = pd.concat(frames).rename(columns={
        "Date": "trade_date", "Open": "open", "High": "high", "Low": "low",
        "Close": "close", "Adj Close": "adj_close", "Volume": "volume"})
    df = df.reset_index(drop=True)
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date
    df["volume"] = df["volume"].astype("Int64")
    df.loc[df["ticker"].str.startswith("^"), "volume"] = pd.NA  # NULL for indexes
    df["source"] = "yfinance"
    df["ingested_at"] = pd.Timestamp.now(tz="UTC").floor("s")
    df["run_id"] = pd.Series([run_id] * len(df), dtype="string", index=df.index)
    return df[COLS]


def to_gcs(df):
    """One parquet per trading day; re-running a date overwrites its file."""
    bucket = storage.Client(project=PROJECT).bucket(BUCKET)
    uris = []
    for d, g in df.groupby("trade_date"):
        path = f"prices/trade_date={d}/prices.parquet"
        buf = io.BytesIO()
        g.to_parquet(buf, index=False, coerce_timestamps="us")
        bucket.blob(path).upload_from_string(buf.getvalue())
        uris.append(f"gs://{BUCKET}/{path}")
    return uris


def to_bigquery(uris, dates):
    """Delete the dates being loaded, then append, so reruns never duplicate."""
    bq = bigquery.Client(project=PROJECT)
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
    a = p.parse_args()
    df = fetch(a.start, a.end, a.run_id)
    print(f"Fetched {len(df)} rows, {df['ticker'].nunique()} tickers, "
          f"{df['trade_date'].nunique()} dates")
    uris = to_gcs(df)
    to_bigquery(uris, sorted(df["trade_date"].unique()))
