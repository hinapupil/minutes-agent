resource "google_storage_bucket" "audio" {
  #checkov:skip=CKV_GCP_62:アクセスログ用バケットの運用はスコープ外。管理操作の監査は Cloud Audit Logs で担保
  #checkov:skip=CKV_GCP_78:録音音声は30日で自動削除する一時データ。versioning で削除済み録音が残る方がプライバシー上有害
  name                        = var.gcs_bucket_name
  location                    = var.region
  uniform_bucket_level_access = true
  force_destroy               = false

  # CKV_GCP_114: 録音音声を誤設定でも公開できないよう強制
  public_access_prevention = "enforced"

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }
}

# Speech-to-Text V2 の batch_recognize は Google 管理の Speech サービスエージェントが
# GCS の音声を直接読む。この権限が無いと文字起こしが
# "storage.objects.get denied" で失敗する（E2E 実測）
resource "google_storage_bucket_iam_member" "speech_service_agent_reader" {
  bucket = google_storage_bucket.audio.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:service-${data.google_project.current.number}@gcp-sa-speech.iam.gserviceaccount.com"
}

data "google_project" "current" {
  project_id = var.project_id
}
