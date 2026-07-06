resource "google_cloud_scheduler_job" "check_actions" {
  name        = "minutes-agent-check-actions"
  description = "Daily action item reminder"
  schedule    = "0 10 * * *"
  time_zone   = "Asia/Tokyo"
  region      = var.region

  http_target {
    http_method = "POST"
    uri         = "${google_cloud_run_v2_service.agent.uri}/tasks/check-actions"

    oidc_token {
      service_account_email = google_service_account.agent.email
      audience              = "${google_cloud_run_v2_service.agent.uri}/tasks/check-actions"
    }

    headers = {
      "Content-Type" = "application/json"
    }

    body = base64encode("{}")
  }
}
