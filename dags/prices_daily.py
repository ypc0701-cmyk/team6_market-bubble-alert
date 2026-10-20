"""Lane 1 daily pipeline: yfinance (Tiingo fallback) -> GCS -> BigQuery raw.prices_raw.

Runs weekdays at 22:00 UTC (6pm ET), after US market close.
Needs on the deployment: Airflow connection google_cloud_default (service account key)
and secret env vars TIINGO_API_KEY and SLACK_WEBHOOK_URL.

Tasks: extract_and_load >> dbt_build
dbt_build runs `dbt build --target prod` (staging + marts + seed + tests). The prod target
writes to datasets `staging` and `marts`; any other target writes to `*_<target>` (see
dbt/macros/generate_schema_name.sql). A failing model or test fails the run and alerts Slack.
"""
from datetime import datetime, timedelta

import pendulum
from airflow.sdk import dag, get_current_context, task

DBT_BIN = "/usr/local/airflow/dbt_venv/bin/dbt"
DBT_PROJECT_DIR = "/usr/local/airflow/dbt"


def notify_slack_on_failure(context):
    """Posts to Slack when a task fails for good (after retries). Needs secret env var SLACK_WEBHOOK_URL."""
    import os

    import requests

    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("SLACK_WEBHOOK_URL not set; skipping Slack alert")
        return
    ti = context["ti"]
    text = (f":red_circle: *{ti.dag_id}* failed\n"
            f"Task: `{ti.task_id}` | Run: `{context.get('run_id')}`\n"
            f"Error: {context.get('exception')}\n"
            f"Log: {getattr(ti, 'log_url', 'see Airflow UI')}")
    requests.post(url, json={"text": text}, timeout=10)


@dag(
    dag_id="prices_daily",
    schedule="0 22 * * 1-5",
    start_date=datetime(2026, 10, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"owner": "lane1", "retries": 2, "retry_delay": timedelta(minutes=5),
                  "on_failure_callback": notify_slack_on_failure},
    tags=["lane1", "ingestion"],
    params={"force_fail": False},  # trigger with force_fail=true to test alerting
)
def prices_daily():

    @task
    def extract_and_load():
        import json

        from airflow.sdk import Connection
        from google.oauth2 import service_account

        from extractor.extract import fetch, to_bigquery, to_gcs

        ctx = get_current_context()
        if ctx["params"].get("force_fail"):
            from airflow.exceptions import AirflowFailException
            raise AirflowFailException("Deliberate failure to test alerting (force_fail=true)")
        end = (ctx.get("data_interval_end") or pendulum.now("UTC")).date()
        start = end - timedelta(days=5)  # re-pull a few days so late corrections land; reruns are idempotent
        key = Connection.get("google_cloud_default").extra_dejson["keyfile_dict"]
        creds = service_account.Credentials.from_service_account_info(
            key if isinstance(key, dict) else json.loads(key))

        df = fetch(start, end, ctx["run_id"])
        uris = to_gcs(df, credentials=creds)
        to_bigquery(uris, sorted(df["trade_date"].unique()), credentials=creds)
        return {"rows": len(df), "tickers": int(df["ticker"].nunique()),
                "sources": sorted(df["source"].unique().tolist())}

    @task(retries=1)
    def dbt_build():
        import json
        import os
        import subprocess
        import tempfile

        from airflow.exceptions import AirflowFailException
        from airflow.sdk import Connection

        key = Connection.get("google_cloud_default").extra_dejson["keyfile_dict"]
        key = key if isinstance(key, str) else json.dumps(key)

        with tempfile.TemporaryDirectory() as tmp:
            keyfile = os.path.join(tmp, "key.json")
            with open(keyfile, "w") as f:
                f.write(key)
            with open(os.path.join(tmp, "profiles.yml"), "w") as f:
                f.write(
                    "ai_bubble_monitor:\n"
                    "  target: prod\n"
                    "  outputs:\n"
                    "    prod:\n"
                    "      type: bigquery\n"
                    "      method: service-account\n"
                    "      project: market-bubble-alert\n"
                    "      dataset: marts\n"
                    f"      keyfile: {keyfile}\n"
                    "      location: US\n"
                    "      threads: 4\n"
                    "      job_execution_timeout_seconds: 600\n"
                )
            env = {**os.environ,
                   "DBT_TARGET_PATH": os.path.join(tmp, "target"),
                   "DBT_LOG_PATH": os.path.join(tmp, "logs")}
            cmd = [DBT_BIN, "build", "--target", "prod",
                   "--profiles-dir", tmp, "--project-dir", DBT_PROJECT_DIR]
            print("Running:", " ".join(cmd))
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
            print(result.stdout)
            if result.returncode != 0:
                print(result.stderr)
                # Show the summary line (e.g. "Done. PASS=118 WARN=0 ERROR=2") in the Slack alert
                tail = [ln for ln in result.stdout.splitlines() if "Done." in ln or "ERROR" in ln][-3:]
                raise AirflowFailException("dbt build failed: " + " | ".join(tail))

    extract_and_load() >> dbt_build()


prices_daily()
