"""Guarded Phase 2 BigQuery ML training entrypoint."""

import argparse
import subprocess

from validate_phase2_training import validate_training_data, run_dbt, DBT_TARGET

TRAINING_MACROS = [
    "train_phase2_logistic_dev",
    "train_phase2_remaining_dev",
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually retrain the four BigQuery ML models",
    )
    args = parser.parse_args()

    if DBT_TARGET != "dev":
        raise RuntimeError(
            "Production training is not enabled yet."
        )

    # Refresh and test upstream data before validating training.
    print("Refreshing Phase 2 features and labels...", flush=True)

    run_dbt([
        "build",
        "--select",
        "weekly_features",
        "weekly_labels",
        "phase2_training_input",
        "phase2_train_rows",
    ])

    # Mandatory R3 validation before any model replacement.
    validate_training_data()

    if not args.execute:
        print(
            "DRY RUN PASSED: R3 gate passed; "
            "no models were retrained.",
            flush=True,
        )
        return

    for macro in TRAINING_MACROS:
        print(f"Running training macro: {macro}", flush=True)
        run_dbt(["run-operation", macro])

    print("All four BigQuery ML training operations completed.")


if __name__ == "__main__":
    main()
