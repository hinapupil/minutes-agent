# GitHub Actions → GCP の keyless 認証 (Workload Identity Federation)
# deploy.yml が google-github-actions/auth で使う。長寿命のサービスアカウント鍵を
# GitHub Secrets に置かないための構成 (docs/runbooks/github-repo-setup.md 参照)

resource "google_iam_workload_identity_pool" "github_actions" {
  workload_identity_pool_id = "github-actions"
  display_name              = "GitHub Actions"
  description               = "deploy.yml からの OIDC 認証"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github_actions.workload_identity_pool_id
  workload_identity_pool_provider_id = "github"
  display_name                       = "GitHub"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
  }

  # このリポジトリの main ブランチの workflow 以外からのトークンを拒否する (CKV_GCP_125)。
  # deploy.yml は push:main と workflow_dispatch（main 上で実行）のみなので sub をブランチまで固定できる
  attribute_condition = "assertion.sub == \"repo:${var.github_repository}:ref:refs/heads/main\""
}

resource "google_service_account" "deploy" {
  account_id   = "github-deploy"
  display_name = "GitHub Actions deploy"
  description  = "deploy.yml がイメージ push / Cloud Run デプロイ / GCE reset に使う"
}

# リポジトリの GitHub Actions だけが deploy SA を借用できる
resource "google_service_account_iam_member" "deploy_wif" {
  service_account_id = google_service_account.deploy.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github_actions.name}/attribute.repository/${var.github_repository}"
}

# deploy.yml の各ステップに必要な最小権限
resource "google_project_iam_member" "deploy_artifact_writer" {
  project = var.project_id
  role    = "roles/artifactregistry.writer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_run_developer" {
  project = var.project_id
  role    = "roles/run.developer"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_project_iam_member" "deploy_compute_admin" {
  project = var.project_id
  role    = "roles/compute.instanceAdmin.v1"
  member  = "serviceAccount:${google_service_account.deploy.email}"
}

# Cloud Run サービス（agent SA で動く）を更新するには actAs が必要
resource "google_service_account_iam_member" "deploy_actas_agent" {
  service_account_id = google_service_account.agent.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

resource "google_service_account_iam_member" "deploy_actas_bot" {
  service_account_id = google_service_account.bot.name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deploy.email}"
}

output "workload_identity_provider" {
  value       = google_iam_workload_identity_pool_provider.github.name
  description = "GitHub Secrets の GCP_WORKLOAD_IDENTITY_PROVIDER に設定する値"
}

output "deploy_service_account" {
  value       = google_service_account.deploy.email
  description = "GitHub Secrets の GCP_DEPLOY_SERVICE_ACCOUNT に設定する値"
}
