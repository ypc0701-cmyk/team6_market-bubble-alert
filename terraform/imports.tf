# These resources were created by hand on Oct 11 to unblock Lane 1.
# The import blocks bring them under Terraform management without recreating them.

import {
  to = google_storage_bucket.landing
  id = "market-bubble-alert-landing"
}

import {
  to = google_bigquery_dataset.layer["raw"]
  id = "projects/market-bubble-alert/datasets/raw"
}

import {
  to = google_bigquery_dataset.layer["staging"]
  id = "projects/market-bubble-alert/datasets/staging"
}

import {
  to = google_bigquery_dataset.layer["marts"]
  id = "projects/market-bubble-alert/datasets/marts"
}

import {
  to = google_service_account.airflow_pipeline
  id = "projects/market-bubble-alert/serviceAccounts/airflow-pipeline@market-bubble-alert.iam.gserviceaccount.com"
}
