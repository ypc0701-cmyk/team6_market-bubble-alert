"""Build Phase 2 predictions using current BigQuery model metadata."""

import subprocess

from validate_phase2_training import (
    ROOT,
    DBT_BIN,
    DBT_PROJECT_DIR,
    DBT_PROFILES_DIR,
    DBT_TARGET,
)

from google.cloud import bigquery

PROJECT = "market-bubble-alert"
DATASET = "marts_dev"

MODELS = (
    "baseline_drawdown",
    "baseline_vol",
    "logistic",
    "boosted_trees",
)




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

    if DBT_TARGET != "dev":
        raise RuntimeError(
            "Production predictions are not enabled yet."
        )
    command = [
        str(DBT_BIN),
        "build",
        "--select",
        "model_predictions",
        "--project-dir",
        str(DBT_PROJECT_DIR),
        "--profiles-dir",
        str(DBT_PROFILES_DIR),
        "--target",
        DBT_TARGET,
        "--vars",
        dbt_vars,
    ]

    print("Using live BigQuery model timestamps:", timestamps, flush=True)

    subprocess.run(command, check=True, cwd=ROOT)

    print("Phase 2 predictions build completed successfully.")


if __name__ == "__main__":
    main()
