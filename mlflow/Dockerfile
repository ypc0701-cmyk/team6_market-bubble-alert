FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1 PORT=8080
EXPOSE 8080

# /mnt/gcs is the MLflow bucket, mounted by Cloud Run (see terraform/mlflow.tf).
# Run metadata lives in SQLite on that mount; artifacts go straight to GCS.
# One worker and one instance: SQLite on a bucket mount supports a single writer only.
CMD ["sh", "-c", "mkdir -p /mnt/gcs/backend && exec mlflow server --backend-store-uri sqlite:////mnt/gcs/backend/mlflow.db --artifacts-destination gs://${ARTIFACT_BUCKET}/artifacts --serve-artifacts --host 0.0.0.0 --port ${PORT:-8080} --workers 1"]
