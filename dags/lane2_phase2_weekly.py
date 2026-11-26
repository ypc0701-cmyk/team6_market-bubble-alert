"""Lane 2 Phase 2 development-only weekly workflow."""

from datetime import datetime, timedelta

from airflow.sdk import dag, task

def notify_slack_on_failure(context):
    """Notify Slack when the Lane 2 DAG fails."""
    import os
    import requests

    url = os.environ.get("SLACK_WEBHOOK_URL")
    if not url:
        print("SLACK_WEBHOOK_URL not set; skipping Slack alert")
        return

    ti = context["ti"]
    message = (
        f":red_circle: *{ti.dag_id}* failed\n"
        f"Task: `{ti.task_id}` | Run: `{context.get('run_id')}`\n"
        f"Error: {context.get('exception')}\n"
        f"Log: {getattr(ti, 'log_url', 'see Airflow UI')}"
    )

    requests.post(
        url,
        json={"text": message},
        timeout=10,
    )


@dag(
    dag_id="lane2_phase2_weekly_dev",
    schedule="0 23 * * 0",
    start_date=datetime(2026, 11, 1),
    catchup=False,
    is_paused_upon_creation=True,
    max_active_runs=1,
    default_args={
        "owner": "lane2",
        "retries": 0,
        "retry_delay": timedelta(minutes=5),
        "on_failure_callback": notify_slack_on_failure,
    },
    tags=["lane2", "phase2", "development"],
)
def lane2_phase2_weekly_dev():

    @task
    def run_weekly_pipeline():
        import os
        import subprocess
        import sys

        root = "/usr/local/airflow"
        script = os.path.join(
            root,
            "training",
            "run_phase2_weekly.py",
        )

        command = [
            sys.executable,
            script,
            "--airflow",
        ]

        print("Running Lane 2 development workflow", flush=True)

        subprocess.run(
            command,
            cwd=root,
            check=True,
        )

    run_weekly_pipeline()


lane2_phase2_weekly_dev()
