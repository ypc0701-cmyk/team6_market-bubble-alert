variable "project_id" {
  type    = string
  default = "market-bubble-alert"
}

variable "region" {
  type    = string
  default = "us-east1"
}

variable "location" {
  description = "Multi-region for the bucket and datasets, so GCS loads into BigQuery work"
  type        = string
  default     = "US"
}

variable "api_data_source" {
  description = "Where the model API reads scores: dummy (api/dummy_scores.csv) until model_scores exists, then bigquery"
  type        = string
  default     = "dummy"

  validation {
    condition     = contains(["dummy", "bigquery"], var.api_data_source)
    error_message = "api_data_source must be dummy or bigquery."
  }
}
