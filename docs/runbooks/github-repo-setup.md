# GitHub リポジトリ設定 — Runbook

Design Doc: [docs/design.md](../design.md)

GitHub 側で実施した、コードとして残らない手動設定（リポジトリ設定 UI / API 経由の変更）を記録する。Terraform や GitHub Actions ワークフロー（`.github/workflows/*.yml`）のようにリポジトリにコミットされる設定は対象外。

---

## Phase 1: main ブランチ保護（完了）

### 1-1: 保護ルールの設定

**事前確認:**
- [x] リポジトリは public、owner は個人アカウント（`hinapupil`、org ではない）
- [x] コラボレーター: `hinapupil`（owner/admin）, `MiyaIF`（チームメンバー、admin 権限なし）

**目的:** owner（admin）は自由にマージできるが、admin 権限を持たないコラボレーターはレビュー承認なしにマージできないようにする。

**手順:**
- [ ] `gh api --method PUT repos/<owner>/<repo>/branches/main/protection --input <json>` で以下を設定する:
  ```json
  {
    "required_status_checks": null,
    "enforce_admins": false,
    "required_pull_request_reviews": {
      "required_approving_review_count": 1,
      "dismiss_stale_reviews": true
    },
    "restrictions": null,
    "allow_force_pushes": false,
    "allow_deletions": false,
    "required_linear_history": false,
    "required_conversation_resolution": true
  }
  ```

> [!NOTE]
> `enforce_admins: false` が肝。GitHub は「PR 作成者は自分の PR を承認できない」仕様のため、`enforce_admins: true` にすると owner 自身の PR も他者の承認が無いとマージできなくなる。`enforce_admins: false` であれば admin（owner）は branch protection の強制対象外になり、承認 0 件でもマージできる。一方 admin 権限の無いコラボレーターには `required_approving_review_count: 1` が効く。

> [!WARNING]
> `required_status_checks` を最初から特定の check 名で必須化すると、その check がまだ一度も走っていない（＝ `.github/workflows/ci.yml` がまだ main に存在しない等）リポジトリでは、その check が永久に "pending" のままになり誰もマージできなくなることがある。CI ワークフローが実際に main に存在し、最低1回実行されてから `required_status_checks` を設定すること。本書作成時点ではこの項目は `null`（未設定）のまま。

**確認:**
- [ ] `gh api repos/<owner>/<repo>/branches/main/protection --jq '{required_approving_review_count: .required_pull_request_reviews.required_approving_review_count, enforce_admins: .enforce_admins.enabled}'` で意図した値になっている
- [ ] admin 権限のないアカウントで実際に PR をマージしようとし、ブロックされることを確認する（推奨、未実施）
- [ ] `gh pr merge --admin` で owner がレビュー無しでマージできることを確認する（**実行は実際にマージしたいときだけ**。確認目的だけで打たない）

### 1-2: 既知の経緯

最初 `required_approving_review_count: 0`（PR は必須だが承認は不要）で設定したが、「自分は自由にマージしつつ、自分以外は勝手にマージできないようにしたい」という要件を受けて `1` に変更した。`0` のままだと admin でない `MiyaIF` も無条件でマージできてしまうため、要件を満たさなかった。

---

## Phase 2: Workload Identity Federation（GitHub Actions → GCP 認証）（完了 2026-07-12）

`.github/workflows/deploy.yml` の keyless 認証。**GCP 側リソースはすべて Terraform 定義**（`infra/wif.tf`、PR #29）で、手動 gcloud は使っていない。

### 2-1: 構成（infra/wif.tf）

- Workload Identity Pool `github-actions` + OIDC Provider `github`（issuer: `token.actions.githubusercontent.com`）
- **信頼境界**: `attribute_condition = "assertion.sub == 'repo:hinapupil/minutes-agent:ref:refs/heads/main'"` — このリポジトリの **main ブランチの workflow のみ**認証可能（CKV_GCP_125 準拠）
- deploy 用 SA `github-deploy@...` への権限は**すべてリソース単位**:
  - `artifactregistry.writer`（対象リポジトリのみ）
  - `run.developer`（対象2サービスのみ）
  - `compute.instanceAdmin.v1`（Bot インスタンス1台のみ）
  - `iam.serviceAccountUser`（実行 SA 2つへの actAs）

> [!NOTE]
> 当初 `run.developer` 等をプロジェクトレベルで付与していたが、セキュリティレビューの over-broad-grant 指摘でリソース単位に縮小した。WIF binding も repository 単位の `principalSet` から main ブランチ subject 単位の `principal` に変更。

### 2-2: 手順（実施記録）

- [x] `gcloud services enable sts.googleapis.com`（iamcredentials は有効化済みだった）
- [x] `infra/wif.tf` を追加して `terraform apply`（PR #29）
- [x] GitHub Secrets 登録（値は Terraform output から。**いずれも識別子であり秘密値ではない**）:
  ```bash
  gh secret set GCP_PROJECT_ID --body "minutes-agent-hackathon"
  gh secret set GCP_WORKLOAD_IDENTITY_PROVIDER --body "$(terraform -chdir=infra output -raw workload_identity_provider)"
  gh secret set GCP_DEPLOY_SERVICE_ACCOUNT --body "$(terraform -chdir=infra output -raw deploy_service_account)"
  ```
- [x] `gh workflow enable Deploy`（WIF 未設定期間は失敗が積むため無効化していた）
- [x] `gh workflow run Deploy --ref main` で実走 → **全ステップ成功**（build/push → Cloud Run ×2 → GCE reset）

### 2-3: トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| auth ステップで `unauthorized_client` | attribute_condition と実行ブランチの不一致 | main 以外から dispatch していないか確認。ブランチ運用を変えるなら `wif.tf` の条件を更新（checkov が変数を解決できないためリテラル記述。`var.github_repository` と一致させること） |
| Cloud Run デプロイで `iam.serviceaccounts.actAs` 拒否 | 実行 SA への serviceAccountUser 不足 | `wif.tf` の `deploy_actas_*` を確認 |
