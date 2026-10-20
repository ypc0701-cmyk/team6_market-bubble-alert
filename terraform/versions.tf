terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  # State lives in GCS so anyone on the team can run Terraform.
  # The state bucket itself is created once by hand (see README).
  backend "gcs" {
    bucket = "market-bubble-alert-tfstate"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
