# MLflow tracking server (Phase 2)

Tracks every training run: parameters, metrics, the universe snapshot date and the model version (issue #88).

| Piece | Where |
| --- | --- |
| Server | Cloud Run service `mlflow` (us-east1), scales to zero, at most 1 instance |
| Run metadata | SQLite at `gs://market-bubble-alert-mlflow/backend/mlflow.db`, mounted into the container |
| Artifacts | `gs://market-bubble-alert-mlflow/artifacts/` |
| Identity | Service account `mlflow-server`: read/write on the MLflow bucket only |
| Access | Not public. Only granted members and the `airflow-pipeline` account can call it |
| Image | `us-east1-docker.pkg.dev/market-bubble-alert/mlops/mlflow:2.22.0`, built from this folder |

All of it is defined in [terraform/mlflow.tf](../terraform/mlflow.tf) except the team members' access, which is granted by hand (the repo is public, so emails stay out of the code). Why SQLite and not Cloud SQL: see "MLflow hosting" in [docs/decision_log.md](../docs/decision_log.md).

## First deploy (Lane 5, Cloud Shell)

The image has to exist before Cloud Run can start, so the first deploy has three steps:

    cd terraform
    terraform init
    # 1. Enable the APIs and create the image repository
    terraform apply -target=google_project_service.mlops -target=google_artifact_registry_repository.mlops
    # 2. Build and push the image
    cd ..
    gcloud builds submit mlflow/ --tag us-east1-docker.pkg.dev/market-bubble-alert/mlops/mlflow:2.22.0
    # 3. Create the bucket, service account and Cloud Run service
    cd terraform
    terraform apply

The last step prints `mlflow_url`.

Give each team member access (repeat per person):

    gcloud run services add-iam-policy-binding mlflow --region us-east1 \
      --member="user:NAME@bu.edu" --role="roles/run.invoker"

## Open the UI

    gcloud run services proxy mlflow --region us-east1 --port 5000

Then open http://localhost:5000 (in Cloud Shell: Web Preview, port 5000).

## Log a run from Python

The server is private, so clients send an identity token. MLflow reads it from `MLFLOW_TRACKING_TOKEN`. Use the same MLflow version as the server (`pip install mlflow==2.22.0`).

    export MLFLOW_TRACKING_URI=$(gcloud run services describe mlflow --region us-east1 --format='value(status.url)')
    export MLFLOW_TRACKING_TOKEN=$(gcloud auth print-identity-token)

    import mlflow
    mlflow.set_experiment("drawdown-probability")
    with mlflow.start_run():
        mlflow.log_params({"model": "logreg", "universe_snapshot": "2026-11-14"})
        mlflow.log_metric("auc", 0.61)   # example value

Tokens last one hour; get a new one for each session.

From the Airflow DAG (service account `airflow-pipeline`), fetch the token in Python instead of calling `gcloud`:

    from google.auth.transport.requests import Request
    from google.oauth2 import id_token
    os.environ["MLFLOW_TRACKING_TOKEN"] = id_token.fetch_id_token(Request(), MLFLOW_URL)

## Limits

- **One writer.** SQLite on a bucket mount does not support file locking across machines, so the service runs one instance with one worker. That fits one weekly training job and a few people browsing; parallel training jobs could fail with "database is locked".
- **Cold start.** With no traffic the service scales to zero; the first request after idle takes about 10 to 30 seconds.
- **Recovery.** The bucket is versioned and keeps old versions for 7 days, so a damaged `mlflow.db` can be restored from an earlier version.
