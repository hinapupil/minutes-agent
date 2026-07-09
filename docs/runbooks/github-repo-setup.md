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

## 未完了（次にやるべきこと）

### Workload Identity Federation（GitHub Actions → GCP 認証）

`.github/workflows/deploy.yml`（PR #1）は以下の GitHub Actions Secrets を前提にしている:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

これらは **未設定**。設定には GCP 側で Workload Identity Pool / Provider の作成、デプロイ用サービスアカウントの作成と権限付与、GitHub 側でのリポジトリ Secrets 登録が必要で、いずれも実プロビジョニング操作（個別確認が必要）。

> [!WARNING]
> この作業は PR #1 がマージされ、デプロイ対象のサービスアカウント名（`infra/iam.tf` の `google_service_account.agent` / `google_service_account.bot`）が確定してから着手すること。先に Workload Identity Pool を作っても、対応する Terraform リソースが存在しない状態では紐付け先が定まらない。

着手時はこのファイルに Phase 2 として追記する。
