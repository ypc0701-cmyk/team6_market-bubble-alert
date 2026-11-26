"""Validate Phase 2 training data before replacing BigQuery ML models."""

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DBT_BIN = (
    ROOT / ".venv" / "Scripts" / "dbt.exe"
    if os.name == "nt"
    else ROOT / ".venv" / "bin" / "dbt"
)


def run_dbt(arguments):
    command = [
        str(DBT_BIN),
        *arguments,
        "--project-dir", str(ROOT / "dbt"),
        "--profiles-dir", str(Path.home() / ".dbt"),
        "--target", "dev",
    ]

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
