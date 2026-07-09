resource "google_artifact_registry_repository" "containers" {
  location      = var.region
  repository_id = var.artifact_registry_repository
  description   = "Minutes Agent container images"
  format        = "DOCKER"
}

