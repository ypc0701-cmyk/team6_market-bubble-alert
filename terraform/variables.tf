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
