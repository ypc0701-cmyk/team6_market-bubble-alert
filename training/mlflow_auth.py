"""Authentication for Lane 2's private Cloud Run MLflow server."""

import os

from google.auth.transport.requests import Request
from google.oauth2 import id_token
from google.oauth2 import service_account

DEFAULT_MLFLOW_URL = "https://mlflow-roeklc77pq-ue.a.run.app"


def get_mlflow_token():
    """Obtain a Google-signed ID token for MLflow."""

    audience = os.environ.get(
        "MLFLOW_TRACKING_URI",
        DEFAULT_MLFLOW_URL,
    ).rstrip("/")

    keyfile = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if keyfile:
        credentials = service_account.IDTokenCredentials.from_service_account_file(
            keyfile,
            target_audience=audience,
        )

        credentials.refresh(Request())

        return credentials.token

    return id_token.fetch_id_token(Request(), audience)


def configure_mlflow_auth():
    """Configure the MLflow client to authenticate with Cloud Run."""

    os.environ.setdefault(
        "MLFLOW_TRACKING_URI",
        DEFAULT_MLFLOW_URL,
    )

    # Preserve an existing token from a trusted caller.
    if os.environ.get("MLFLOW_TRACKING_TOKEN"):
        return

    os.environ["MLFLOW_TRACKING_TOKEN"] = get_mlflow_token()
