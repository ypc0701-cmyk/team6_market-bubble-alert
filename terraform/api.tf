# Model API for Phase 2 (issue #89).
# Public Cloud Run service that serves the latest weekly scores.
# Uses the image repository and APIs defined in mlflow.tf.
# See docs/decision_log.md "Public model API".

locals {
  api_image = "${var.region}-docker.pkg.dev/${var.project_id}/mlops/model-api:0.1.0"
}

resource "google_service_account" "model_api" {
  account_id   = "model-api"
  display_name = "Model API (Cloud Run)"
  description  = "Runs the model API; can run queries and read the marts dataset only"
}

# Least privilege, same as dashboard-runtime: run queries, read marts, write nothing.
resource "google_project_iam_member" "model_api_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.model_api.email}"
}

resource "google_bigquery_dataset_iam_member" "model_api_marts_reader" {
  dataset_id = google_bigquery_dataset.layer["marts"].dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.model_api.email}"
}

resource "google_cloud_run_v2_service" "model_api" {
  name                = "model-api"
  location            = var.region
  deletion_protection = false

  template {
    service_account = google_service_account.model_api.email

    scaling {
      min_instance_count = 0
      max_instance_count = 2 # caps cost, like the dashboard
    }

    containers {
      image = local.api_image

      ports {
        container_port = 8080
      }

      env {
        name  = "DATA_SOURCE"
        value = var.api_data_source
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [
    google_project_service.mlops,
    google_project_iam_member.model_api_job_user,
    google_bigquery_dataset_iam_member.model_api_marts_reader,
  ]
}

# Public: reviewers call the API during evaluation without logging in.
resource "google_cloud_run_v2_service_iam_member" "model_api_public" {
  name     = google_cloud_run_v2_service.model_api.name
  location = google_cloud_run_v2_service.model_api.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

output "model_api_url" {
  value = google_cloud_run_v2_service.model_api.uri
}
