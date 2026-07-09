resource "google_artifact_registry_repository" "containers" {
  #checkov:skip=CKV_GCP_84:コンテナイメージは Google 管理鍵で暗号化済み。CSEK/CMEK の鍵運用はハッカソンのスコープ外
  location      = var.region
  repository_id = var.artifact_registry_repository
  description   = "Minutes Agent container images"
  format        = "DOCKER"
}
