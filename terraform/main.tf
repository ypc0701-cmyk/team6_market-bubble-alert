# GCS landing zone for raw extractor files (Lane 1)
resource "google_storage_bucket" "landing" {
  name                        = "market-bubble-alert-landing"
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = false
}

# BigQuery datasets: raw (Lane 1), staging (Lane 2), marts (Lane 3)
# dbt dev datasets (e.g. marts_dev) are created by dbt and not managed here.
resource "google_bigquery_dataset" "layer" {
  for_each = toset(["raw", "staging", "marts"])

  dataset_id                 = each.key
  location                   = var.location
  delete_contents_on_destroy = false
}

# Service account used by the Astronomer DAG
resource "google_service_account" "airflow_pipeline" {
  account_id   = "airflow-pipeline"
  display_name = "Airflow pipeline (Astronomer DAG)"
  description  = "Used by the daily DAG to write to GCS and BigQuery"
}
