resource "google_cloud_tasks_queue" "minutes" {
  name     = var.cloud_tasks_queue
  location = var.region

  rate_limits {
    max_dispatches_per_second = 1
    max_concurrent_dispatches = 2
  }

  retry_config {
    max_attempts       = 3
    min_backoff        = "10s"
    max_backoff        = "300s"
    max_doublings      = 4
    max_retry_duration = "1800s"
  }
}

