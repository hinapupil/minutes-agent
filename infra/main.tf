terraform {
  required_version = ">= 1.7.0"

  # state バケットは Runbook (docs/runbooks/gcp-bootstrap.md Phase 5) で
  # Terraform 管理外として事前作成済み（バージョニング有効）
  backend "gcs" {
    bucket = "minutes-agent-hackathon-tfstate"
    prefix = "minutes-agent"
  }

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

locals {
  api_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/${var.api_image_name}:${var.image_tag}"
  bot_image = "${var.region}-docker.pkg.dev/${var.project_id}/${var.artifact_registry_repository}/${var.bot_image_name}:${var.image_tag}"
}

