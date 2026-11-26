"""Build Phase 2 scores from a verified, machine-readable R6 decision."""

import csv
import json
import subprocess
from pathlib import Path

from google.cloud import bigquery

from validate_phase2_training import (
    ROOT,
    DBT_BIN,
    DBT_PROJECT_DIR,
    DBT_PROFILES_DIR,
    DBT_TARGET,
)

PROJECT = "market-bubble-alert"
DATASET = "marts_dev"

OUTPUT = ROOT / "evaluation" / "output"
DECISION_FILE = OUTPUT / "serving_decision.json"
EVALUATION_CSV = OUTPUT / "model_evaluation.csv"

ALLOWED_MODELS = {
    "baseline_drawdown",
    "baseline_vol",
    "logistic",
    "boosted_trees",
}


def validate_evaluation():
    if not DECISION_FILE.exists() or not EVALUATION_CSV.exists():
        raise FileNotFoundError(
            "Serving decision or evaluation CSV missing. Run evaluation first."
        )

    decision = json.loads(DECISION_FILE.read_text(encoding="utf-8"))

    if (
        decision.get("bigquery_project") != PROJECT
        or decision.get("bigquery_dataset") != DATASET
    ):
        raise ValueError("Serving decision has the wrong BigQuery source")

    served = decision.get("served_model")

    if served not in ALLOWED_MODELS:
        raise ValueError(f"Invalid served model: {served}")

    client = bigquery.Client(project=PROJECT)
    expected = {}

    for name in sorted(ALLOWED_MODELS):
        model_id = f"{PROJECT}.{DATASET}.phase2_{name}_dev"
        raw = client.get_model(model_id).to_api_repr()
        expected[name] = f"{name}-dev-{raw['creationTime']}"

    if decision.get("model_versions") != expected:
        raise ValueError(
            "Serving decision model versions do not match BigQuery"
        )

    with EVALUATION_CSV.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        rows = list(csv.DictReader(file))

    if len(rows) != 80:
        raise ValueError(
            f"Expected 80 evaluation rows; found {len(rows)}"
        )

    keys = set()

    for row in rows:
        name = row["model_name"]

        if name not in expected:
            raise ValueError(f"Unexpected evaluation model: {name}")

        if row["model_version"] != expected[name]:
            raise ValueError(f"Stale evaluation version for {name}")

        if row["evaluated_at"] != decision.get("evaluated_at"):
            raise ValueError("Evaluation timestamp does not match decision")

        key = (
            name,
            row["split"],
            row["population"],
            row["metric"],
        )

        if key in keys:
            raise ValueError(f"Duplicate evaluation record: {key}")

        keys.add(key)

    if len(keys) != 80:
        raise ValueError("Evaluation coverage is incomplete")

    return served


def main():
    if DBT_TARGET != "dev":
        raise RuntimeError(
            "Production scoring is not enabled yet."
        )

    served = validate_evaluation()

    print("Current BigQuery model versions verified.", flush=True)
    print(f"R6 selected served model: {served}", flush=True)

    command = [
        str(DBT_BIN),
        "build",
        "--select", "model_scores",
        "--project-dir", str(DBT_PROJECT_DIR),
        "--profiles-dir", str(DBT_PROFILES_DIR),
        "--target", DBT_TARGET,
        "--vars", f"phase2_served_model: {served}",
    ]

    subprocess.run(command, check=True, cwd=ROOT)

    print(f"Phase 2 scores built successfully using {served}.")


if __name__ == "__main__":
    main()
