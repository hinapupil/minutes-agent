resource "google_cloud_run_v2_service" "agent" {
  name     = var.cloud_run_service_name
  location = var.region

  template {
    service_account                  = google_service_account.agent.email
    timeout                          = "3600s"
    max_instance_request_concurrency = 1

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    containers {
      image = local.api_image

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.audio.name
      }
      env {
        name  = "CLOUD_TASKS_QUEUE"
        value = google_cloud_tasks_queue.minutes.name
      }
      env {
        name  = "DISCORD_APPLICATION_ID"
        value = var.discord_application_id
      }
      env {
        name  = "DISCORD_PUBLIC_KEY"
        value = var.discord_public_key
      }
      env {
        name  = "DISCORD_CHANNEL_ID"
        value = var.discord_channel_id
      }
      env {
        name  = "GEMINI_MODEL"
        value = var.gemini_model
      }
      env {
        name  = "SPEECH_MODEL"
        value = var.speech_model
      }
      env {
        name  = "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL"
        value = google_service_account.agent.email
      }
      env {
        name = "DISCORD_WEBHOOK_URL"
        value_source {
          secret_key_ref {
            secret  = var.discord_webhook_url_secret_id
            version = "latest"
          }
        }
      }
      dynamic "env" {
        for_each = var.gemini_api_key_secret_id == "" ? [] : [var.gemini_api_key_secret_id]
        content {
          name = "GEMINI_API_KEY"
          value_source {
            secret_key_ref {
              secret  = env.value
              version = "latest"
            }
          }
        }
      }
      env {
        name = "AGENT_API_TOKEN"
        value_source {
          secret_key_ref {
            secret  = var.agent_api_token_secret_id
            version = "latest"
          }
        }
      }
    }
  }

  depends_on = [
    google_artifact_registry_repository.containers,
    google_firestore_database.default,
  ]
}
