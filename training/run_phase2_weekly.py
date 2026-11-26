"""Run the Lane 2 Phase 2 development workflow."""

import argparse
import subprocess
import sys
from pathlib import Path

from train_phase2 import main as train_main

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run_script(relative_path, *args):
    command = [PYTHON, str(ROOT / relative_path), *args]
    print(f"Running: {relative_path}", flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--retrain",
        action="store_true",
        help="Replace all four development BigQuery ML models",
    )
    args = parser.parse_args()

    # Always refresh training data and enforce R3.
    run_script("training/train_phase2.py", *(
        ["--execute"] if args.retrain else []
    ))

    # Predictions must reference current BigQuery model versions.
    run_script("training/build_phase2_predictions.py")

    # Run the registered R6/R7 evaluation and write dev results.
    run_script(
        "evaluation/evaluate_phase2.py",
        "--bq-project", "market-bubble-alert",
        "--bq-dataset", "marts_dev",
        "--write-bq",
    )

    # Select the evaluated model and refresh scores.
    run_script("training/build_phase2_scores.py")

    # Log current model versions and metrics to MLflow.
    run_script("training/track_phase2_models.py")

    print("LANE 2 DEVELOPMENT WORKFLOW COMPLETED.", flush=True)


if __name__ == "__main__":
    main()
