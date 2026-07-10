resource "google_compute_instance" "bot" {
  #checkov:skip=CKV_GCP_38:ブートディスクは Google 管理鍵で暗号化済み。CSEK/CMEK の鍵運用はハッカソンのスコープ外
  #checkov:skip=CKV_GCP_40:Discord Gateway への常時 egress に外部 IP が必要。Cloud NAT 化は将来課題（受信側は GCP デフォルト firewall で保護）
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

  # CKV_GCP_32: プロジェクト共通 SSH 鍵でのログインを遮断（メンテは OS Login / IAP 経由を想定）
  metadata = {
    block-project-ssh-keys = "true"
  }

  # CKV_GCP_39: Shielded VM（ブート改ざん検知）
  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
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
    cloud_tasks_service_account   = google_service_account.agent.email
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
    google_cloud_run_v2_service.interactions,
  ]
}
