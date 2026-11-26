"""Shared dbt execution and R3 training validation for Lane 2."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_DBT = (
    ROOT / ".venv" / "Scripts" / "dbt.exe"
    if os.name == "nt"
    else ROOT / ".venv" / "bin" / "dbt"
)

DBT_BIN = os.environ.get(
    "LANE2_DBT_BIN",
    str(DEFAULT_DBT),
)

DBT_PROJECT_DIR = Path(
    os.environ.get("LANE2_DBT_PROJECT_DIR", str(ROOT / "dbt"))
)

DBT_PROFILES_DIR = Path(
    os.environ.get("LANE2_DBT_PROFILES_DIR", str(Path.home() / ".dbt"))
)

DBT_TARGET = os.environ.get("LANE2_DBT_TARGET", "dev")


def run_dbt(arguments):
    command = [
        str(DBT_BIN),
        *arguments,
        "--project-dir", str(DBT_PROJECT_DIR),
        "--profiles-dir", str(DBT_PROFILES_DIR),
        "--target", DBT_TARGET,
    ]

    print("Running dbt:", " ".join(command), flush=True)

    subprocess.run(command, check=True, cwd=ROOT)


def validate_training_data():
    print("Checking R3 training base-rate gate...", flush=True)

    run_dbt([
        "test",
        "--select",
        "phase2_label_base_rate_in_band",
    ])

    print("R3 validation passed. Training is permitted.", flush=True)


if __name__ == "__main__":
    validate_training_data()
