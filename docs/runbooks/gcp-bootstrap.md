# GCP インフラ ブートストラップ — Runbook

Design Doc: [docs/design.md](../design.md)（13. Schedule のインフラ担当トラック）

「インフラ担当」が GCP プロジェクトをゼロから使える状態にするまでの手順。ローカル開発環境の `gcloud` セットアップから、プロジェクト作成・請求・予算アラート・必要 API の有効化までを対象とする。`infra/`（Terraform）での実リソース作成・`terraform apply` は対象外（別 Runbook）。

> [!IMPORTANT]
> **本番運用の課金が発生するフェーズを含む。Phase 3（請求先アカウントの紐付け）以降は実行前にプロジェクトオーナーへ確認すること。**

---

## Phase 1: ローカル gcloud CLI の準備（5〜15分）

### 1-1: gcloud の動作確認

**事前確認:**
- [x] Homebrew がインストール済み
- [ ] `gcloud --version` が正常に実行できる

**手順:**
- [ ] `gcloud --version` を実行する
- [ ] `ModuleNotFoundError: No module named 'imp'` 等のエラーが出る場合、gcloud-cli のバージョンが古く、インストール済み Python（3.12 以降）で削除済みの `imp` モジュールに依存している可能性が高い
  - 確認: `cat /opt/homebrew/Caskroom/gcloud-cli/latest/google-cloud-sdk/VERSION`（数百番台前半 〜 例: 367.0.0 など、現行の 5xx 系より大きく古い場合は要更新）
  - 確認: `brew info --cask gcloud-cli` で Homebrew 側の最新版番号と比較する

> [!NOTE]
> gcloud-cli は Homebrew Cask の `auto_updates` タグが付いているため、`brew upgrade` の通常チェックでは更新対象として検出されないことがある。古いまま放置されているケースに注意。

**手順（更新が必要な場合）:**
- [ ] `brew reinstall --cask gcloud-cli` を実行する

> [!WARNING]
> Homebrew のアンインストールフェーズで、過去のインストールが残した一部ファイルの削除に `sudo` パスワードが必要になることがある。非対話シェル（CI・エージェントの Bash ツール等）では `sudo` のパスワードプロンプトに応答できず失敗する。その場合はユーザー自身の対話端末（ターミナル）で実行してもらうこと。

**確認:**
- [ ] `gcloud --version` で現行バージョン（執筆時点 575.0.0 系）が表示される
- [ ] `bundled-python3-unix` のバージョンが表示される（gcloud 同梱 Python が使われていることの確認）

### 1-2: GCP 認証

**手順:**
- [ ] `gcloud auth list` で既存の認証アカウントを確認する
- [ ] `invalid_grant: Bad Request` 等のエラーが出る場合、トークンが失効しているので再認証する

> [!NOTE]
> `gcloud auth login` はブラウザでの OAuth 同意フローが必要なため対話実行必須。非対話シェルからは完了できない。

**確認:**
- [ ] `gcloud auth list` の `ACTIVE` 列に `*` が付いた状態で目的のアカウントが表示される

---

## Phase 2: GCP プロジェクト作成（5分）

### 2-1: プロジェクト ID の決定と作成

**事前確認:**
- [x] プロジェクト名の候補を決めておく（例: `minutes-agent-hackathon`）

> [!NOTE]
> GCP のプロジェクト ID は全世界で一意。`<service-name>` のようなシンプルな ID は高確率で既に使用済み。`<service-name>-<用途/年度等のサフィックス>` を最初から使うと無駄打ちが減る。

**手順:**
- [ ] `gcloud projects create <PROJECT_ID> --name="<表示名>"` を実行する
- [ ] `ERROR: ... already in use` が出たら別の ID で再試行する

> [!WARNING]
> 候補を複数同時に（ループ等で）試す場合、**1つ成功したら即座にループを止めること**。本 Runbook の作成時、候補を `for` ループで順に試した際に途中で抜けるロジックを書き忘れ、4つの候補すべてでプロジェクトが作成されてしまう事故があった。`gcloud projects create` はリトライ前提のコマンドではなく、成功すれば即座に実環境にリソースが作られる。

**手順（誤って複数作成してしまった場合のリカバリ）:**
- [ ] 残すプロジェクト ID を1つ決める
- [ ] 不要なプロジェクトを `gcloud projects delete <PROJECT_ID> --quiet` で削除する
- [ ] `gcloud projects describe <PROJECT_ID> --format="value(lifecycleState)"` で `DELETE_REQUESTED` になっていることを確認する

> [!NOTE]
> `gcloud projects delete` は即時の完全削除ではない。30日間は `gcloud projects undelete <PROJECT_ID>` で復元可能な猶予期間（`DELETE_REQUESTED` 状態）があり、その後完全削除される。

**確認:**
- [ ] `gcloud projects list --filter="projectId:<prefix>*" --format="table(projectId,name,lifecycleState)"` で意図したプロジェクトのみ `ACTIVE` であることを確認する

### 2-2: デフォルトプロジェクトの設定

**手順:**
- [ ] `gcloud config set project <PROJECT_ID>`

**確認:**
- [ ] `gcloud config list` の `[core] project` が期待値になっている

---

## Phase 3: 請求先アカウントの紐付け・予算アラート（10分）

> [!WARNING]
> このフェーズ以降は実際の課金が発生し得る。実行前に必ずプロジェクトオーナー（人間）の明示的な合意を取ること。

### 3-1: 請求先アカウントの紐付け

**事前確認:**
- [ ] `gcloud billing accounts list` で利用可能な請求先アカウントを確認する
- [ ] 紐付け先の請求先アカウントの支払い方法（クレジットカード等）が有効か、Cloud Console の課金ページ（`https://console.cloud.google.com/billing/<ACCOUNT_ID>/paymentmethods`）で確認する
  - gcloud CLI のレスポンスには支払い方法（カード番号・有効期限等）は含まれない（API 非公開）ため、確認は Console で行う

**手順:**
- [ ] `gcloud billing projects link <PROJECT_ID> --billing-account=<BILLING_ACCOUNT_ID>` を実行する

**確認:**
- [ ] `gcloud billing projects describe <PROJECT_ID>` の `billingEnabled` が `true` になっている

### 3-2: 予算アラートの設定

**事前確認:**
- [ ] 月額予算の上限を決める（想定ワークロード: Cloud Run min-instances=1 + GCE e2-small 常時稼働 + Speech-to-Text/Gemini API のハッカソン規模利用、で概算）
- [ ] `gcloud services list --enabled --project=<PROJECT_ID> | grep billingbudgets` で Cloud Billing Budget API が有効か確認する

**手順:**
- [ ] 未有効の場合: `gcloud services enable billingbudgets.googleapis.com --project=<PROJECT_ID>`
- [ ] `gcloud billing budgets create --billing-account=<BILLING_ACCOUNT_ID> --display-name="<表示名>" --budget-amount=<金額><通貨コード(例: JPY)> --filter-projects=projects/<PROJECT_ID> --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0`

> [!NOTE]
> `--filter-projects` は `projects/<PROJECT_ID>` 形式（プロジェクト番号ではなくプロジェクト ID 文字列でよい）。閾値到達時はデフォルトで請求先アカウントの管理者・閲覧者にメール通知される（Pub/Sub 通知を別途使う場合は `--notifications-rule-*` フラグで設定）。

**確認:**
- [ ] コマンドの出力に予算オブジェクトの UUID が表示される（`Created [<uuid>]`）
- [ ] Cloud Console の「お支払い」→「予算とアラート」に表示されることを確認する（推奨、Runbook 実行者が目視で確認）

---

## Phase 4: 必要 API の有効化（5分）

### 4-1: 必要 API の洗い出し

**手順:**
- [ ] `infra/*.tf` の `resource "google_xxx_yyy"` から対応する API を洗い出す
- [ ] `docs/design.md` とアプリの `.env.example` から実行時に呼ぶ GCP サービス（Speech-to-Text、Gemini 等）を洗い出す

> [!NOTE]
> 本プロジェクト（minutes-agent）で確認した対応表:
>
> | Terraform リソース / アプリ依存 | 必要 API |
> |---|---|
> | `google_cloud_run_v2_service` | `run.googleapis.com` |
> | `google_compute_instance`（GCE Bot） | `compute.googleapis.com` |
> | `google_firestore_database` | `firestore.googleapis.com` |
> | `google_storage_bucket` | `storage.googleapis.com` |
> | `google_cloud_tasks_queue` | `cloudtasks.googleapis.com` |
> | `google_cloud_scheduler_job` | `cloudscheduler.googleapis.com` |
> | `google_artifact_registry_repository` | `artifactregistry.googleapis.com` |
> | `google_service_account` / IAM member 系 | `iam.googleapis.com`, `cloudresourcemanager.googleapis.com` |
> | Speech-to-Text V2（`agent/tools/transcribe.py`） | `speech.googleapis.com` |
> | Gemini via Vertex AI（`GEMINI_API_KEY` 未設定時のデフォルト経路） | `aiplatform.googleapis.com` |
> | Gemini via API Key（`GEMINI_API_KEY` 設定時の経路） | `generativelanguage.googleapis.com` |
> | Secret Manager（Cloud Run の `value_source.secret_key_ref`、GCE startup script） | `secretmanager.googleapis.com` |
> | 予算アラート（Phase 3-2） | `billingbudgets.googleapis.com` |

### 4-2: 一括有効化

**手順:**
- [ ] `gcloud services enable <api1> <api2> ... --project=<PROJECT_ID>` で一括有効化する（個別に `enable` するより早い）

**確認:**
- [ ] `gcloud services list --enabled --project=<PROJECT_ID>` に列挙した API が全て含まれている

---

## Phase 5: Terraform state backend 用 GCS バケット（5分）

`infra/main.tf`（PR #1）は本書作成時点で `backend "gcs" {}` を定義しておらず、Terraform state の保管先が未確定だった。`terraform apply` を誰がいつ実行しても同じ state を共有できるよう、先にリモート state 用バケットを用意する。

> [!WARNING]
> **このフェーズはユーザーへの個別確認なしに実行してはならない。** 本書の作成過程で、エージェントが「インフラ実装をどんどん進めて」という大枠の指示を根拠に、このバケット作成についてだけ個別の確認を取らずに実行してしまい、Claude Code の auto mode classifier に事後的にブロックされる事故があった。Phase 3 と同様、実費用が発生する/実リソースを作る操作は「大枠の許可」では実行せず、その都度具体的に確認を取ること。

**事前確認:**
- [ ] バケット名の候補を決める（例: `<PROJECT_ID>-tfstate`）。GCS バケット名も全世界一意
- [ ] `gsutil ls -b gs://<BUCKET_NAME>` で名前が空いているか確認する（`BucketNotFoundException` なら空き）

**手順:**
- [ ] `gcloud storage buckets create gs://<BUCKET_NAME> --project=<PROJECT_ID> --location=<REGION> --uniform-bucket-level-access`
- [ ] `gcloud storage buckets update gs://<BUCKET_NAME> --versioning`（state ファイル破損時に過去バージョンへ復元できるようにする）

**確認:**
- [ ] `gcloud storage buckets describe gs://<BUCKET_NAME> --format="value(name,location,versioning_enabled,uniform_bucket_level_access)"` で意図した設定になっている

**フォローアップ（このバケット自体の作成では完結しない）:**
- [ ] `infra/main.tf` に以下を追加する Terraform PR を別途出す:
  ```hcl
  terraform {
    backend "gcs" {
      bucket = "<BUCKET_NAME>"
      prefix = "minutes-agent"
    }
  }
  ```
- [ ] 既存の local state がある場合は `terraform init -migrate-state` で移行する

---

## Phase 6: Terraform 初期化とシークレット投入（10分）

Phase 5 のフォローアップとして `infra/main.tf` に `backend "gcs"` を追加済み（本 Phase 追記と同じ PR）。`terraform apply` の前提となる初期化と、Secret Manager へのランタイムシークレット投入を行う。

### 6-1: Application Default Credentials（ADC）

`gcloud auth login`（Phase 1）だけでは Terraform は認証できない。Terraform の google provider と GCS backend はユーザー資格情報ではなく **ADC** を使うため、別途セットアップが必要（ブラウザでの対話認証）:

- [ ] `gcloud auth application-default login`

> [!NOTE]
> ADC 未設定のまま `terraform init` すると `storage.NewClient() failed: ... could not find default credentials` で失敗する（実際に発生）。エージェント実行環境では対話認証を代行できないため、この手順はユーザー自身の端末で実行する。

### 6-2: terraform init

- [ ] `just tf-init`（= `terraform -chdir=infra init`。provider ダウンロード + GCS backend 接続確認。リソース作成・課金なし）
- [ ] `terraform -chdir=infra validate` が pass する

### 6-3: シークレット投入（Secret Manager）

シークレットの**値**の置き場所は Secret Manager のみとする。設計判断:

| 案 | 採否 | 理由 |
|---|---|---|
| Secret Manager に値、Terraform は名前(ID)のみ参照 | ✅ 採用 | 値が tfstate/git/CI に一切残らない。Cloud Run/GCE は `secret_key_ref` + `secretAccessor` で実行時に読む（`infra/cloud_run.tf`/`gce.tf` で配線済み） |
| GitHub Secrets に値を入れて CI から投入 | ❌ | 真実の情報源が2つになる。GitHub Secrets は deploy.yml 用の識別子（プロジェクトID・WIF provider 名・SA email）だけに使う |
| `google_secret_manager_secret_version` で Terraform から値を投入 | ❌ | 値が tfstate に平文で保存される |

手順（値は隠し入力で受け取り、シェル履歴・argv に残らない）:

- [ ] `just secrets-init` — 対話で `discord-bot-token` / `discord-webhook-url` を投入し、`agent-api-token` は自動生成
- [ ] Gemini を API キーで使う場合のみ `just secret-set gemini-api-key`（Vertex AI/ADC 経由なら不要。その場合 `terraform.tfvars` で `gemini_api_key_secret_id = ""`）
- [ ] `gcloud secrets list --project=<PROJECT_ID>` で登録を確認

---

## ロールバック手順

### Phase 2 のロールバック

- [ ] `gcloud projects delete <PROJECT_ID> --quiet`（30日間は `gcloud projects undelete <PROJECT_ID>` で復元可能）

### Phase 3 のロールバック

- [ ] 予算アラート削除: `gcloud billing budgets list --billing-account=<BILLING_ACCOUNT_ID>` で ID を確認し `gcloud billing budgets delete <BUDGET_ID> --billing-account=<BILLING_ACCOUNT_ID>`
- [ ] 請求先アカウントの紐付け解除: `gcloud billing projects unlink <PROJECT_ID>`（以降そのプロジェクトの有料リソースは順次停止に向かうため、先に Phase 4 で有効化したリソースの後始末を検討すること）

### Phase 4 のロールバック

- [ ] `gcloud services disable <api> --project=<PROJECT_ID>`（依存関係がある場合は `--force` が必要なことがある。安易な `--force` は他リソースを壊しうるので個別に確認すること）

### Phase 5 のロールバック

- [ ] `infra/main.tf` に `backend "gcs"` を追加済みなら、先に state を別の場所へ退避してからバケットを消すこと（state を失うと Terraform が既存リソースを見失う）
- [ ] `gcloud storage rm -r gs://<BUCKET_NAME>`（versioning が有効なため、過去バージョンも含めて完全に削除するには `-r` に加えてバケット自体の削除が必要: `gcloud storage buckets delete gs://<BUCKET_NAME>`）

---

## トラブルシューティング

| 症状 | 原因 | 対処 |
|---|---|---|
| `gcloud` 実行時に `ModuleNotFoundError: No module named 'imp'` | gcloud-cli が古いバージョンのまま放置され、Python 3.12+ で削除された `imp` モジュールに依存している | `brew reinstall --cask gcloud-cli`（sudo が必要な場合はユーザーの対話端末で実行） |
| `gcloud auth list` 後の操作で `invalid_grant: Bad Request` | 認証トークンの失効 | `gcloud auth login` で再認証（対話・ブラウザ必須） |
| `gcloud projects create` で `already in use by another project` | プロジェクト ID は全世界一意。希望 ID が既に使われている | サフィックスを変えて再試行。**1回の試行ごとに成否を確認してから次へ進む（ループで全候補を試さない）** |
| `gcloud billing budgets create` で `Cloud Billing Budget API has not been used in project ... SERVICE_DISABLED` | `billingbudgets.googleapis.com` が未有効化 | `gcloud services enable billingbudgets.googleapis.com --project=<PROJECT_ID>` してから再実行 |
| `gcloud billing projects link` を打とうとしたら自動承認フレームワークにブロックされた | 課金紐付けのような実費用が発生する操作は、エージェント実行環境によっては自動許可されず人間の明示確認が必要 | プロジェクトオーナーに対象の請求先アカウント ID を明示して確認を取った上で再実行する |
| `gcloud storage buckets create` 等の実プロビジョニング操作だけ事後的に harness にブロックされた | 「インフラ実装を進めて」のような大枠の許可は、その配下の個別の実リソース作成操作まで自動承認しない。大枠の指示だけを根拠に実費用が発生する操作を進めるとブロックされうる | 実リソースを作る/課金が発生する操作は、大枠の指示とは別にその都度具体的に確認を取ってから実行する |

---

## 再実行時に変更すべきパラメータ

別プロジェクト・別環境でこの Runbook を再利用する場合に差し替える値:

| パラメータ | 本書での値 | 備考 |
|---|---|---|
| `PROJECT_ID` | `minutes-agent-hackathon` | 用途・年度等のサフィックスを変えて衝突回避 |
| `BILLING_ACCOUNT_ID` | `01C4A5-D18BE2-81C16D` | `gcloud billing accounts list` で確認 |
| 予算上限額 | ¥10,000/月 | ワークロード規模（Cloud Run/GCE の常時稼働有無、Speech-to-Text/Gemini の利用量見込み）に応じて見直す |
| 必要 API リスト | Phase 4-1 の表を参照 | `infra/*.tf` の差分に応じて随時更新する |
| tfstate バケット名 | `minutes-agent-hackathon-tfstate` | `<PROJECT_ID>-tfstate` のように命名すると衝突しにくい |
| tfstate バケットのリージョン | `asia-northeast1` | `infra/variables.tf` の `region` デフォルト値と合わせる |
