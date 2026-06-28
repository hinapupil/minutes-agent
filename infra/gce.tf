resource "google_compute_instance" "bot" {
  name         = var.gce_instance_name
  zone         = var.zone
  machine_type = "e2-small"

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-12"
      size  = 20
      type  = "pd-balanced"
    }
  }

  network_interface {
    network = "default"
    access_config {}
  }

  service_account {
    email = google_service_account.bot.email
    scopes = [
      "https://www.googleapis.com/auth/cloud-platform",
    ]
  }

  metadata_startup_script = templatefile("${path.module}/templates/bot-startup.sh.tftpl", {
    project_id                    = var.project_id
    region                        = var.region
    bot_image                     = local.bot_image
    gcs_bucket_name               = google_storage_bucket.audio.name
    cloud_tasks_queue             = google_cloud_tasks_queue.minutes.name
    cloud_run_base_url            = google_cloud_run_v2_service.agent.uri
    discord_application_id        = var.discord_application_id
    discord_channel_id            = var.discord_channel_id
    discord_bot_token_secret_id   = var.discord_bot_token_secret_id
    discord_webhook_url_secret_id = var.discord_webhook_url_secret_id
    gemini_model                  = var.gemini_model
    agent_api_token_secret_id     = var.agent_api_token_secret_id
  })

  depends_on = [
    google_artifact_registry_repository.containers,
    google_cloud_run_v2_service.agent,
  ]
}
