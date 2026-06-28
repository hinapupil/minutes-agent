output "cloud_run_url" {
  value       = google_cloud_run_v2_service.agent.uri
  description = "Cloud Run Agent API URL"
}

output "gce_instance_name" {
  value       = google_compute_instance.bot.name
  description = "Discord bot GCE instance name"
}

output "gcs_bucket_name" {
  value       = google_storage_bucket.audio.name
  description = "Audio storage bucket"
}

output "artifact_registry_repository" {
  value       = google_artifact_registry_repository.containers.name
  description = "Artifact Registry repository"
}

