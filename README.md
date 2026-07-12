# Minutes Agent

Discord の定例ミーティングの会議アカウンタビリティ（説明責任・実行責任）を自律的に管理する AI エージェント。

Bot が自ら voice channel に参加して録音し、文字起こし → 議事録生成 → アクションアイテム抽出 → Discord 投稿までを全自動で行う。会議と会議の間ではアクションアイテムの追跡・リマインド・過去議事録の横断検索を自律的に実行する。

- **稼働中のデモ**: <https://minutes-agent-interactions-uj5jsuakcq-an.a.run.app/>（動作確認の手順つき）
- **設計文書**: [docs/design.md](docs/design.md)

## アーキテクチャ

```
GCE: Discord Bot (Pycord)      → voice 録音
         ↓
Cloud Tasks                    → 非同期ジョブ
         ↓
Cloud Run: Agent API           → Speech-to-Text + 議事録生成（内部）
Cloud Run: Interactions        → Discord slash command 応答（公開）
         ↓
Firestore + Cloud Storage      → データ永続化
         ↓
Discord Webhook                → 結果投稿
```

## コマンド

| コマンド | 説明 |
|---------|------|
| `/join` | voice channel に参加して録音開始（確認ボタンつき） |
| `/stop` | 録音停止 → 議事録生成 |
| `/minutes <file>` | 音声ファイル / zip から議事録生成（手動フォールバック） |
| `/ask <question>` | 過去の議事録に関する質問 |
| `/actions` | 未完了アクションアイテム一覧 |
| `/action-done <id>` | アクションアイテムを完了 |
| `/setup <owner/repo>` | GitHub リポジトリから用語集を学習（音声認識の固有名詞補正） |

## 技術スタック

- **AI**: Gemini 3.5 Flash, Speech-to-Text API (V2), ADK
- **Compute**: Cloud Run, GCE
- **Data**: Firestore, Cloud Storage
- **Bot**: Pycord（Python。voice 受信は upstream PR #3159 を SHA 固定で採用）
- **IaC**: Terraform
- **CI/CD**: GitHub Actions（WIF keyless 認証）

## 開発環境

[Devbox](https://www.jetify.com/devbox) で再現可能な開発環境を提供する（Python 3.12, ffmpeg,
Pycord voice 録音用の libopus, [just](https://github.com/casey/just),
[lefthook](https://github.com/evilmartians/lefthook) + [gitleaks](https://github.com/gitleaks/gitleaks)）:

```bash
curl -fsSL https://get.jetify.com/devbox | bash   # 必要なら Nix も自動で入る
direnv allow                                       # または devbox shell
just setup                                         # 依存と git hooks を導入
just --list                                        # タスク一覧
```

`lefthook` がコミットごとに `gitleaks`、push ごとに `just check`（lint + typecheck + test）を実行する。
規約とセキュリティ方針は [AGENTS.md](AGENTS.md) を参照。

## ローカル実行

```bash
just dev-api   # Cloud Run API をローカル起動
just dev-bot   # Discord Bot をローカル起動
just check     # lint + typecheck + test
```

必要な環境変数は `.env.example` に列挙している。

## ディレクトリ構成

- `bot/`: Pycord slash commands、voice 録音、GCS アップロード、Cloud Tasks enqueue
- `api/`: Cloud Run FastAPI アプリ、Cloud Tasks ハンドラ、Discord Interactions エンドポイント
- `agent/`: ADK エージェント定義とツール
- `minutes_agent/`: 共有層（config、models、Firestore、Cloud Storage、Cloud Tasks、Discord 通知、workflow、用語集）
- `infra/`: Terraform（Cloud Run、GCE、Firestore、GCS、Cloud Tasks、Cloud Scheduler、WIF、IAM）

## デプロイ

main への push で GitHub Actions（`.github/workflows/deploy.yml`）が
イメージのビルド → Artifact Registry push → Cloud Run ×2 デプロイ → GCE Bot 再起動まで行う。
認証は Workload Identity Federation（キーレス）。

インフラの初期構築は Terraform:

```bash
cd infra
terraform init
terraform apply
```

Discord アプリは録音 Bot 用と Interactions 用の 2 つに分離している（理由は
[ADR-0002](docs/adr/0002-split-discord-apps-for-gateway-and-interactions.md)、
セットアップ手順は [Runbook: Discord 設定](docs/runbooks/discord-setup.md)）。

シークレットの置き場所:

- GitHub Secrets（識別子のみ）: `GCP_PROJECT_ID`, `GCP_WORKLOAD_IDENTITY_PROVIDER`, `GCP_DEPLOY_SERVICE_ACCOUNT`
- Secret Manager（秘匿値）: `DISCORD_BOT_TOKEN`, `DISCORD_WEBHOOK_URL`, `AGENT_API_TOKEN` ほか

## ドキュメント

- [設計文書](docs/design.md)
- [ドメイン用語集（CONTEXT.md）](CONTEXT.md)
- [Architecture Decision Records](docs/adr/)
- [Runbooks（GCP / GitHub / Discord のセットアップ）](docs/runbooks/)

## 録音まわりの実装メモ

Discord の voice は DAVE（E2EE）化が進んでおり、旧受信プロトコルはサーバー側で拒否される。
本プロジェクトは Pycord upstream の DAVE 対応（PR #3159）を SHA 固定で採用し、
互換シム `CompatWaveSink` と AST ベースの契約テストで追従している
（詳細は [design.md §5.1](docs/design.md)）。`/minutes <file>` は録音に依存しない手動経路として維持している。

## ライセンス

MIT

## ハッカソン

[DevOps × AI Agent Hackathon](https://findy.co.jp/4127/) (Findy × Google Cloud)

`#findy_hackathon`
