# Lane 2 — Phase 2 Training and Airflow Handoff

## Status

The development workflow has been executed successfully against
market-bubble-alert.marts_dev.

The Airflow DAG and service-account authentication adapter have passed
local syntax and mock tests. They have NOT been validated inside the
deployed Astro runtime.

Production deployment is not enabled.

## Implemented components

- Weekly feature engineering and forward-looking labels
- R3 training base-rate validation
- Four BigQuery ML models:
  - baseline_drawdown
  - baseline_vol
  - logistic
  - boosted_trees
- Versioned model predictions
- Lane 3 R6/R7 evaluation
- Machine-readable serving decision
- Version-validated model scores
- MLflow experiment tracking

## Validated development results

- Training rows: 21,813
- Training label base rate: 23.22%
- Prediction rows: 170,928
- Scored ticker-weeks: 42,732
- Evaluation metric rows: 80
- MLflow model-version runs: 4
- Current R6 served model: baseline_vol

These counts describe the validated development run. They are not
guaranteed to remain constant after new data or model retraining.

## Local development execution

From the repository root, with the Python environment and dbt profile
configured:

    .\.venv\Scripts\python.exe training\run_phase2_weekly.py

To explicitly retrain all four development models:

    .\.venv\Scripts\python.exe training\run_phase2_weekly.py --retrain

Retraining replaces existing development BigQuery ML models.
Do not use --retrain unless replacement is intended.

The workflow runs training-data refresh and R3 validation, predictions,
evaluation, scoring, and MLflow tracking in sequence.

## Airflow integration

DAG: dags/lane2_phase2_weekly.py

DAG ID: lane2_phase2_weekly_dev

Proposed schedule: Sunday at 23:00 UTC

The DAG starts paused, allows one active run, and does not automatically
retrain models.

Airflow entrypoint:

    python training/run_phase2_weekly.py --airflow

The credentials adapter expects google_cloud_default to contain a
service-account JSON key in keyfile_dict.

It creates temporary credentials and a dbt profile, then configures:

- GOOGLE_APPLICATION_CREDENTIALS
- LANE2_DBT_BIN
- LANE2_DBT_PROJECT_DIR
- LANE2_DBT_PROFILES_DIR
- LANE2_DBT_TARGET=dev

The development dbt target resolves Phase 2 marts to marts_dev.

MLflow tracking uses a Google-signed ID token for the private
Cloud Run service.

## Dependencies

Airflow Python dependencies are listed in the root requirements.txt.
The lightweight MLflow client is mlflow-skinny==2.22.0.

dbt uses the separate virtual environment defined in Dockerfile.

training/requirements.txt documents the full local MLflow dependency
configuration.

## Outstanding deployment validation

Before unpausing the DAG:

1. Verify that the Astro image includes training/, evaluation/, and dbt/.
2. Confirm Airflow imports the DAG without errors.
3. Confirm the Airflow task can retrieve google_cloud_default.
4. Verify service-account authentication against the private MLflow URL.
5. Verify BigQuery and dbt development permissions.
6. Verify writable evaluation/output/ storage.
7. Execute a controlled development run and inspect all task logs.
8. Confirm model version consistency and MLflow tracking results.
9. Review ID-token expiration and refresh behavior.
10. Confirm scheduling, operational ownership, and failure alerts.

Local Python tests and dependency resolution have passed, but a live
Astro container build and Airflow execution have not been performed.

## Safety limitations

- Production training, prediction, scoring, and tracking are disabled.
- The development workflow must not be treated as production deployment.
- The Airflow service-account key must never be committed to Git.
- Generated evaluation outputs are ignored by Git.
- The new weekly DAG must remain paused until live validation succeeds.

## GitHub

Branch: lane2/phase2-features-labels

Draft PR: https://github.com/ypc0701-cmyk/team6_market-bubble-alert/pull/103

The approved modeling and evaluation rules are documented in
docs/decision_log.md and docs/schema_contract_v0.3.md.
