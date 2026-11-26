"""Track existing Lane 2 BigQuery ML models in MLflow."""

import csv
import json
import os
from pathlib import Path

import mlflow
from google.cloud import bigquery
from mlflow.tracking import MlflowClient

PROJECT = "market-bubble-alert"
DATASET = "marts_dev"
EXPERIMENT = "phase2-bigquery-ml-dev"
SERVED_MODEL = "baseline_vol"

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_CSV = ROOT / "evaluation/output/model_evaluation.csv"

MODELS = [
    "baseline_drawdown",
    "baseline_vol",
    "logistic",
    "boosted_trees",
]


def collect_model_metadata():
    client = bigquery.Client(project=PROJECT)
    records = []

    for name in MODELS:
        model_id = f"{PROJECT}.{DATASET}.phase2_{name}_dev"
        raw = client.get_model(model_id).to_api_repr()

        runs = raw.get("trainingRuns", [])
        latest_run = runs[-1] if runs else {}

        records.append({
            "model_name": name,
            "bigquery_model_id": model_id,
            "model_type": raw.get("modelType"),
            "model_version": f"{name}-dev-{raw['creationTime']}",
            "trained_at_ms": int(raw["creationTime"]),
            "training_started_at": latest_run.get("startTime"),
            "training_options": latest_run.get("trainingOptions", {}),
        })

    return records


def build_tracking_records():
    with EVALUATION_CSV.open(
        newline="", encoding="utf-8-sig"
    ) as file:
        evaluation = list(csv.DictReader(file))

    records = []

    for model in collect_model_metadata():
        matching = [
            row for row in evaluation
            if row["model_name"] == model["model_name"]
            and row["model_version"] == model["model_version"]
        ]

        if len(matching) != 20:
            raise ValueError(
                f"{model['model_name']}: expected 20 evaluation metrics, "
                f"found {len(matching)}"
            )

        metrics = {}

        for row in matching:
            key = (
                f"{row['split']}__"
                f"{row['population']}__"
                f"{row['metric']}"
            )

            if key in metrics:
                raise ValueError(f"Duplicate metric: {key}")

            metrics[key] = float(row["value"])

        records.append({**model, "metrics": metrics})

    return records


def register_models():
    if not os.environ.get("MLFLOW_TRACKING_URI"):
        raise RuntimeError("MLFLOW_TRACKING_URI is not configured")

    if not os.environ.get("MLFLOW_TRACKING_TOKEN"):
        raise RuntimeError("MLFLOW_TRACKING_TOKEN is not configured")

    records = build_tracking_records()

    mlflow.set_experiment(EXPERIMENT)
    client = MlflowClient()

    experiment = client.get_experiment_by_name(EXPERIMENT)

    for record in records:
        version = record["model_version"]

        existing = client.search_runs(
            experiment_ids=[experiment.experiment_id],
            filter_string=f"tags.model_version = '{version}'",
            max_results=1,
        )

        if existing:
            print(f"SKIPPED existing version: {version}")
            continue

        with mlflow.start_run(run_name=version):
            mlflow.set_tags({
                "model_name": record["model_name"],
                "model_version": version,
                "bigquery_model_id": record["bigquery_model_id"],
                "model_type": record["model_type"],
                "environment": "dev",
                "storage_type": "bigquery_ml_reference",
                "selected_for_serving": str(
                    record["model_name"] == SERVED_MODEL
                ).lower(),
            })

            mlflow.log_params({
                "bigquery_project": PROJECT,
                "bigquery_dataset": DATASET,
                "trained_at_ms": record["trained_at_ms"],
                "training_started_at":
                    record["training_started_at"] or "",
            })

            for key, value in record["training_options"].items():
                if isinstance(value, (dict, list)):
                    value = json.dumps(value)

                mlflow.log_param(
                    f"bqml_{key}", str(value)
                )

            mlflow.log_metrics(record["metrics"])

            print(
                f"REGISTERED {version}: "
                f"{len(record['metrics'])} metrics"
            )


if __name__ == "__main__":
    register_models()
