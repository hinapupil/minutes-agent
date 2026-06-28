terraform {
  required_version = ">= 1.7.0"

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

