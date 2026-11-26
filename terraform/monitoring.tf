# Phase 2 monitoring, API health (issue #91).
# Definitions: docs/phase2_monitoring.md section 4 (Lane 3). Plumbing: Lane 5.
#
# Alerts go to an email notification channel named "Lane 5 alerts", created once
# by hand (see api/README.md) so no email address is stored in this public repo.

resource "google_project_service" "monitoring" {
  service            = "monitoring.googleapis.com"
  disable_on_destroy = false
}

data "google_monitoring_notification_channel" "lane5" {
  display_name = "Lane 5 alerts"
  type         = "email"
}

locals {
  # Cloud Monitoring allows at most about 24 hours minus the metric's ingestion
  # delay per window, so "past 24 hours" is measured as 23 hours.
  api_alert_window = "82800s"
  api_filter       = "resource.type = \"cloud_run_revision\" AND resource.label.service_name = \"model-api\""
}

resource "google_monitoring_alert_policy" "api_5xx" {
  display_name = "model-api: 5xx share above 1%"
  combiner     = "OR"

  conditions {
    display_name = "5xx responses / all responses > 1% over ~24h"
    condition_threshold {
      filter             = "${local.api_filter} AND metric.type = \"run.googleapis.com/request_count\" AND metric.label.response_code_class = \"5xx\""
      denominator_filter = "${local.api_filter} AND metric.type = \"run.googleapis.com/request_count\""
      comparison         = "COMPARISON_GT"
      threshold_value    = 0.01
      duration           = "0s"

      aggregations {
        alignment_period     = local.api_alert_window
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.service_name"]
      }
      denominator_aggregations {
        alignment_period     = local.api_alert_window
        per_series_aligner   = "ALIGN_DELTA"
        cross_series_reducer = "REDUCE_SUM"
        group_by_fields      = ["resource.label.service_name"]
      }

      # No requests means nothing to judge, not an outage.
      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  notification_channels = [data.google_monitoring_notification_channel.lane5.name]
  alert_strategy {
    auto_close = "604800s"
  }
  documentation {
    content   = "More than 1% of model API requests returned 5xx over the past day. Check Cloud Run logs for service model-api. Definition: docs/phase2_monitoring.md section 4."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.monitoring]
}

resource "google_monitoring_alert_policy" "api_latency" {
  display_name = "model-api: p95 latency above 2 s"
  combiner     = "OR"

  conditions {
    display_name = "p95 request latency > 2000 ms over ~24h"
    condition_threshold {
      filter          = "${local.api_filter} AND metric.type = \"run.googleapis.com/request_latencies\""
      comparison      = "COMPARISON_GT"
      threshold_value = 2000 # milliseconds
      duration        = "0s"

      aggregations {
        alignment_period     = local.api_alert_window
        per_series_aligner   = "ALIGN_PERCENTILE_95"
        cross_series_reducer = "REDUCE_MAX"
        group_by_fields      = ["resource.label.service_name"]
      }

      evaluation_missing_data = "EVALUATION_MISSING_DATA_INACTIVE"
    }
  }

  notification_channels = [data.google_monitoring_notification_channel.lane5.name]
  alert_strategy {
    auto_close = "604800s"
  }
  documentation {
    content   = "The model API's p95 latency was above 2 seconds over the past day. With few requests, cold starts (the service scales to zero) can cause this on their own. Definition: docs/phase2_monitoring.md section 4."
    mime_type = "text/markdown"
  }

  depends_on = [google_project_service.monitoring]
}
