"""Lane 1 daily pipeline: yfinance (Tiingo fallback) -> GCS -> BigQuery raw.prices_raw.

Runs weekdays at 22:00 UTC (6pm ET), after US market close.
Needs on the deployment: Airflow connection google_cloud_default (service account key)
and secret env var TIINGO_API_KEY. A dbt task is added once Lane 2's project is ready.
"""
from datetime import datetime, timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task


@dag(
    dag_id="prices_daily",
    schedule="0 22 * * 1-5",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "lane1", "retries": 2, "retry_delay": timedelta(minutes=5)},
    tags=["lane1", "ingestion"],
)
def prices_daily():

    @task
    def extract_and_load():
        from airflow.providers.google.common.hooks.base_google import GoogleBaseHook

        from extractor.extract import fetch, to_bigquery, to_gcs

        ctx = get_current_context()
        end = (ctx.get("data_interval_end") or pendulum.now("UTC")).date()
        start = end - timedelta(days=5)  # re-pull a few days so late corrections land; reruns are idempotent
        creds = GoogleBaseHook(gcp_conn_id="google_cloud_default").get_credentials()

        df = fetch(start, end, ctx["run_id"])
        uris = to_gcs(df, credentials=creds)
        to_bigquery(uris, sorted(df["trade_date"].unique()), credentials=creds)
        return {"rows": len(df), "tickers": int(df["ticker"].nunique()),
                "sources": sorted(df["source"].unique().tolist())}

    extract_and_load()


prices_daily()
