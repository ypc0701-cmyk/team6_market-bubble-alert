"""Temporary Google Cloud credentials and dbt profile for Lane 2 Airflow."""

import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

PROJECT = "market-bubble-alert"


@contextmanager
def airflow_credentials():
    """Configure Lane 2 using Airflow's existing Google Cloud connection."""

    from airflow.sdk import Connection

    key = Connection.get(
        "google_cloud_default"
    ).extra_dejson["keyfile_dict"]

    if isinstance(key, str):
        key = json.loads(key)

    if key.get("type") != "service_account":
        raise ValueError(
            "google_cloud_default must contain service-account credentials"
        )

    with tempfile.TemporaryDirectory(prefix="lane2_") as tmp:
        directory = Path(tmp)
        keyfile = directory / "key.json"
        profile = directory / "profiles.yml"

        keyfile.write_text(
            json.dumps(key),
            encoding="utf-8",
        )

        # Restrict file permissions where supported.
        if os.name != "nt":
            keyfile.chmod(0o600)

        profile.write_text(
            "ai_bubble_monitor:\n"
            "  target: dev\n"
            "  outputs:\n"
            "    dev:\n"
            "      type: bigquery\n"
            "      method: service-account\n"
            f"      project: {PROJECT}\n"
            "      dataset: marts\n"
            f"      keyfile: '{keyfile.as_posix()}'\n"
            "      location: US\n"
            "      threads: 4\n"
            "      job_execution_timeout_seconds: 900\n",
            encoding="utf-8",
        )

        previous = {
            name: os.environ.get(name)
            for name in (
                "GOOGLE_APPLICATION_CREDENTIALS",
                "LANE2_DBT_PROFILES_DIR",
                "LANE2_DBT_TARGET",
                "LANE2_DBT_BIN",
                "LANE2_DBT_PROJECT_DIR",
                "MLFLOW_TRACKING_TOKEN",
            )
        }

        try:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(keyfile)
            os.environ["LANE2_DBT_PROFILES_DIR"] = str(directory)
            os.environ["LANE2_DBT_TARGET"] = "dev"
            os.environ["LANE2_DBT_BIN"] = (
                "/usr/local/airflow/dbt_venv/bin/dbt"
            )
            os.environ["LANE2_DBT_PROJECT_DIR"] = (
                "/usr/local/airflow/dbt"
            )

            # A pre-existing local token must not override Airflow identity.
            os.environ.pop("MLFLOW_TRACKING_TOKEN", None)

            yield
        finally:
            for name, value in previous.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value
