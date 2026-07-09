# Minutes Agent

Discord の定例ミーティングにおける会議のアカウンタビリティ（説明責任・実行責任）を自律的に管理する AI エージェント。

Bot が自ら voice channel に参加して録音し、文字起こし → 議事録生成 → アクションアイテム抽出 → Discord 投稿までを全自動で行う。会議と会議の間ではアクションアイテムの追跡・リマインド・過去議事録の横断検索を自律的に実行する。

## Architecture

```
GCE: Discord Bot (Pycord)     → Voice Recording
         ↓
Cloud Tasks                    → 非同期ジョブ
         ↓
Cloud Run: Agent API           → Speech-to-Text + 議事録生成
Cloud Run: Interactions        → Discord slash command webhook
         ↓
Firestore + Cloud Storage      → データ永続化
         ↓
Discord Webhook                → 結果投稿
```

## Commands

| Command | Description |
|---------|-------------|
| `/join` | Voice channel に参加して録音開始 |
| `/stop` | 録音停止 → 議事録生成 |
| `/ask <question>` | 過去の議事録に関する質問 |
| `/actions` | 未完了アクションアイテム一覧 |
| `/action-done <id>` | アクションアイテムを完了 |

## Tech Stack

- **AI**: Gemini 3.5 Flash, Speech-to-Text API, ADK
- **Compute**: Cloud Run, GCE
- **Data**: Firestore, Cloud Storage
- **Bot**: Pycord (Python)
- **IaC**: Terraform
- **CI/CD**: GitHub Actions

## Development Environment

Reproducible dev environment via [Devbox](https://www.jetify.com/devbox) (Python 3.12, ffmpeg,
libopus for Pycord voice recording, [just](https://github.com/casey/just),
[lefthook](https://github.com/evilmartians/lefthook) + [gitleaks](https://github.com/gitleaks/gitleaks)):

```bash
curl -fsSL https://get.jetify.com/devbox | bash   # installs Nix automatically if needed
direnv allow                                       # or: devbox shell
just setup                                         # installs deps + git hooks
just --list                                        # see all available tasks
```

`lefthook` runs `gitleaks` on every commit and `just check` (lint + typecheck + test) on every
push. See [AGENTS.md](AGENTS.md) for conventions and security notes.

## Documentation

- [Design Document](docs/design.md)

## Local Development

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

API:

```powershell
uvicorn api.main:app --reload --port 8080
```

Discord Bot:

```powershell
python -m bot.main
```

Required environment variables are listed in `.env.example`.

## App Implementation Scope

- `bot/`: Pycord slash commands, voice recording, GCS upload, Cloud Tasks enqueue
- `api/`: Cloud Run FastAPI app, Cloud Tasks handlers, Discord Interactions endpoint
- `agent/`: ADK agent definition and tools
- `minutes_agent/`: shared config, models, Firestore, Cloud Storage, Cloud Tasks, Discord notification, workflow
- `infra/`: Terraform resources for Cloud Run, GCE, Firestore, GCS, Cloud Tasks, Cloud Scheduler, IAM

## Verification

```powershell
ruff check .
mypy minutes_agent api agent bot
pytest
```

## Deployment

Terraform:

```powershell
cd infra
terraform init
terraform apply
```

Terraform outputs `discord_interactions_url`. Set that value as the Discord Interactions endpoint.

GitHub Actions:

- `.github/workflows/ci.yml`: lint, type check, tests
- `.github/workflows/deploy.yml`: build/push API and Bot images, deploy Cloud Run, restart GCE Bot

Required GitHub secrets for deploy:

- `GCP_PROJECT_ID`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOY_SERVICE_ACCOUNT`

Required Secret Manager secrets:

- `DISCORD_BOT_TOKEN`
- `DISCORD_WEBHOOK_URL`
- `AGENT_API_TOKEN`
- `GEMINI_API_KEY` when not using Vertex AI credentials

## Known Runtime Constraint

Pycord 2.8.0 exposes `start_recording()` / `WaveSink`, but current Discord voice reception can be affected by DAVE end-to-end encryption. `/minutes` accepts an audio file or zip as the specified fallback path.

## License

MIT

## Hackathon

[DevOps × AI Agent Hackathon](https://findy.co.jp/4127/) (Findy × Google Cloud)

`#findy_hackathon`
