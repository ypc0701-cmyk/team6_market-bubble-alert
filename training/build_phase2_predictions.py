"""Build Phase 2 predictions using current BigQuery model metadata."""

import os
import subprocess
import sys
from pathlib import Path

from google.cloud import bigquery

PROJECT = "market-bubble-alert"
DATASET = "marts_dev"

MODELS = (
    "baseline_drawdown",
    "baseline_vol",
    "logistic",
    "boosted_trees",
)

ROOT = Path(__file__).resolve().parents[1]


def get_model_timestamps():
    client = bigquery.Client(project=PROJECT)
    timestamps = {}

    for name in MODELS:
        model_id = f"{PROJECT}.{DATASET}.phase2_{name}_dev"
        raw = client.get_model(model_id).to_api_repr()

        timestamps[name] = int(raw["creationTime"])

    return timestamps


def main():
    timestamps = get_model_timestamps()

    yaml_lines = ["phase2_model_timestamps:"]

    for name in MODELS:
        yaml_lines.append(f"  {name}: {timestamps[name]}")

    dbt_vars = "\n".join(yaml_lines)

    dbt_executable = (
        ROOT / ".venv" / "Scripts" / "dbt.exe"
        if os.name == "nt"
        else ROOT / ".venv" / "bin" / "dbt"
    )

    if not dbt_executable.exists():
        raise FileNotFoundError(
            f"dbt executable not found: {dbt_executable}"
        )

    command = [
        str(dbt_executable),
        "build",
        "--select",
        "model_predictions",
        "--project-dir",
        str(ROOT / "dbt"),
        "--profiles-dir",
        str(Path.home() / ".dbt"),
        "--target",
        "dev",
        "--vars",
        dbt_vars,
    ]

    print("Using live BigQuery model timestamps:", timestamps, flush=True)

    subprocess.run(command, check=True, cwd=ROOT)

    print("Phase 2 predictions build completed successfully.")


if __name__ == "__main__":
    main()
