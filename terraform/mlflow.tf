# MLflow tracking server for Phase 2 (issue #88).
# Cloud Run (scales to zero) + one GCS bucket that holds both the run metadata
# (SQLite, mounted into the container) and the model artifacts.
# See docs/decision_log.md "MLflow hosting" for why no Cloud SQL.

locals {
  mlflow_image = "${var.region}-docker.pkg.dev/${var.project_id}/mlops/mlflow:2.22.0"
}

resource "google_project_service" "mlops" {
  for_each = toset([
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
  ])
  service            = each.key
  disable_on_destroy = false
}

# Docker images for Phase 2 services (MLflow now, the model API next)
resource "google_artifact_registry_repository" "mlops" {
  repository_id = "mlops"
  location      = var.region
  format        = "DOCKER"
  description   = "Phase 2 images: MLflow server and model API"
  depends_on    = [google_project_service.mlops]
}

# Run metadata (backend/mlflow.db) and artifacts (artifacts/)
resource "google_storage_bucket" "mlflow" {
  name                        = "${var.project_id}-mlflow"
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  # Versioning lets us roll mlflow.db back if a write ever corrupts it.
  versioning {
    enabled = true
  }

  # Keep old versions for 7 days only, so the frequently rewritten
  # mlflow.db does not pile up storage.
  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 7
      with_state                 = "ARCHIVED"
    }
    action {
      type = "Delete"
    }
  }
}

resource "google_service_account" "mlflow_server" {
  account_id   = "mlflow-server"
  display_name = "MLflow server (Cloud Run)"
  description  = "Runs the MLflow tracking server; read/write on the MLflow bucket only"
}

# Least privilege: the server can use its own bucket and nothing else.
resource "google_storage_bucket_iam_member" "mlflow_server" {
  bucket = google_storage_bucket.mlflow.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.mlflow_server.email}"
}

resource "google_cloud_run_v2_service" "mlflow" {
  name                = "mlflow"
  location            = var.region
  deletion_protection = false

  template {
    service_account       = google_service_account.mlflow_server.email
    execution_environment = "EXECUTION_ENVIRONMENT_GEN2" # needed for the bucket mount

    scaling {
      min_instance_count = 0 # scale to zero: no cost when idle
      max_instance_count = 1 # SQLite on a bucket mount: one writer only
    }

    containers {
      image = local.mlflow_image

      ports {
        container_port = 8080
      }

      env {
        name  = "ARTIFACT_BUCKET"
        value = google_storage_bucket.mlflow.name
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
      }

      volume_mounts {
        name       = "mlflow-bucket"
        mount_path = "/mnt/gcs"
      }
    }

    volumes {
      name = "mlflow-bucket"
      gcs {
        bucket    = google_storage_bucket.mlflow.name
        read_only = false
      }
    }
  }

  depends_on = [
    google_project_service.mlops,
    google_storage_bucket_iam_member.mlflow_server,
  ]
}

# Not public: only granted identities can open MLflow.
# Terraform grants the DAG's account so the weekly training task can log runs.
# Team members are granted by hand (see mlflow/README.md): the repo is public,
# so their emails stay out of the code. This binding is additive and does not
# remove the hand-added members.
resource "google_cloud_run_v2_service_iam_member" "mlflow_pipeline" {
  name     = google_cloud_run_v2_service.mlflow.name
  location = google_cloud_run_v2_service.mlflow.location
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.airflow_pipeline.email}"
}

output "mlflow_url" {
  value = google_cloud_run_v2_service.mlflow.uri
}
