variable "project_id" {
  type        = string
  description = "Google Cloud project ID"
}

variable "region" {
  type        = string
  description = "Primary Google Cloud region"
  default     = "asia-northeast1"
}

variable "zone" {
  type        = string
  description = "GCE zone for the Discord bot"
  default     = "asia-northeast1-a"
}

variable "artifact_registry_repository" {
  type        = string
  description = "Artifact Registry repository name"
  default     = "minutes-agent"
}

variable "api_image_name" {
  type        = string
  description = "Cloud Run API image name"
  default     = "api"
}

variable "bot_image_name" {
  type        = string
  description = "Discord bot image name"
  default     = "bot"
}

variable "image_tag" {
  type        = string
  description = "Container image tag"
  default     = "latest"
}

variable "cloud_run_service_name" {
  type        = string
  description = "Cloud Run service name"
  default     = "minutes-agent-api"
}

variable "interactions_cloud_run_service_name" {
  type        = string
  description = "Public Cloud Run service name for Discord Interactions"
  default     = "minutes-agent-interactions"
}

variable "gce_instance_name" {
  type        = string
  description = "GCE instance name for the Discord bot"
  default     = "minutes-agent-bot"
}

variable "gcs_bucket_name" {
  type        = string
  description = "Cloud Storage bucket for meeting audio"
}

variable "cloud_tasks_queue" {
  type        = string
  description = "Cloud Tasks queue name"
  default     = "minutes-agent"
}

variable "discord_channel_id" {
  type        = string
  description = "Default Discord text channel ID"
}

variable "discord_application_id" {
  type        = string
  description = "Discord application ID (recording bot app; Gateway-connected, no endpoint URL)"
}

variable "discord_public_key" {
  type        = string
  description = "Discord public key (recording bot app)"
}

# ADR-0002: Interactions Endpoint と Gateway は同一アプリで両立しないため、
# Cloud Run interactions サービス用に別アプリの資格情報を分離する
variable "interactions_discord_application_id" {
  type        = string
  description = "Discord application ID (interactions app; receives HTTP interactions on Cloud Run)"
}

variable "interactions_discord_public_key" {
  type        = string
  description = "Discord public key (interactions app; used for Ed25519 signature verification)"
}

variable "discord_bot_token_secret_id" {
  type        = string
  description = "Secret Manager secret ID for DISCORD_BOT_TOKEN"
}

variable "discord_webhook_url_secret_id" {
  type        = string
  description = "Secret Manager secret ID for DISCORD_WEBHOOK_URL"
}

variable "gemini_api_key_secret_id" {
  type        = string
  description = "Secret Manager secret ID for GEMINI_API_KEY"
  default     = ""
}

variable "agent_api_token_secret_id" {
  type        = string
  description = "Secret Manager secret ID for AGENT_API_TOKEN"
}

variable "gemini_model" {
  type        = string
  description = "Gemini model"
  default     = "gemini-3.5-flash"
}

variable "speech_model" {
  type        = string
  description = "Speech-to-Text V2 model"
  default     = "chirp_2"
}
