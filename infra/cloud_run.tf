resource "google_cloud_run_v2_service" "agent" {
  name     = var.cloud_run_service_name
  location = var.region
  # ハッカソン環境: 審査後の撤収(destroy)と失敗リビジョンの置き換えを可能にする
  deletion_protection = false

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
      # ADK 内部の google-genai を Vertex AI モードで動かす（無いと API キーを
      # 要求して /ask の Agent 実行が ValueError: No API key で落ちる。E2E実測）
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
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
        name  = "MINUTES_AGENT_ROUTE_PROFILE"
        value = "internal"
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

resource "google_cloud_run_v2_service" "interactions" {
  name     = var.interactions_cloud_run_service_name
  location = var.region
  # ハッカソン環境: 審査後の撤収(destroy)と失敗リビジョンの置き換えを可能にする
  deletion_protection = false

  template {
    service_account                  = google_service_account.agent.email
    timeout                          = "3600s"
    max_instance_request_concurrency = 1

    scaling {
      # Discord Interactions は 3 秒以内の初期応答が必須で、cold start だと
      # 間に合わず「時間内に応答しませんでした」になる。常時 1 台ウォームに保つ
      min_instance_count = 1
      max_instance_count = 3
    }

    containers {
      image = local.api_image

      # /ask 等は Discord への deferred 応答後に BackgroundTasks で処理を続けるため、
      # リクエスト外 CPU スロットリングを無効化する（無いと処理が飢餓状態でハングする。E2E実測）
      resources {
        cpu_idle = false
      }

      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "GOOGLE_CLOUD_LOCATION"
        value = var.region
      }
      # ADK 内部の google-genai を Vertex AI モードで動かす（無いと API キーを
      # 要求して /ask の Agent 実行が ValueError: No API key で落ちる。E2E実測）
      env {
        name  = "GOOGLE_GENAI_USE_VERTEXAI"
        value = "true"
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
        name  = "CLOUD_RUN_BASE_URL"
        value = google_cloud_run_v2_service.agent.uri
      }
      env {
        name  = "MINUTES_AGENT_ROUTE_PROFILE"
        value = "public"
      }
      env {
        name  = "CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL"
        value = google_service_account.agent.email
      }
      env {
        name  = "DISCORD_APPLICATION_ID"
        value = var.interactions_discord_application_id
      }
      env {
        name  = "DISCORD_PUBLIC_KEY"
        value = var.interactions_discord_public_key
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
    google_cloud_run_v2_service.agent,
    google_firestore_database.default,
  ]
}
