# Project Instructions

## Quick Start

```bash
direnv allow   # or: devbox shell
just setup     # install dependencies and git hooks
just dev-api   # start the Cloud Run API locally
just dev-bot   # start the Discord bot locally
just check     # lint + typecheck + test (full local check)
```

Devbox provides a reproducible dev environment (Python 3.12, ffmpeg, libopus
for Pycord voice recording, just, lefthook, gitleaks) so setup is identical
across macOS/Linux without manual installs.

## Architecture

```
bot/            # Pycord slash commands, voice recording, GCS upload, Cloud Tasks enqueue
api/            # Cloud Run FastAPI app, Cloud Tasks handlers, Discord Interactions endpoint
agent/          # ADK agent definition and tools
minutes_agent/  # shared config, models, Firestore, Cloud Storage, Cloud Tasks, Discord notification, workflow
infra/          # Terraform: Cloud Run, GCE, Firestore, GCS, Cloud Tasks, Cloud Scheduler, IAM
docs/           # design document
```

See [docs/design.md](docs/design.md) for the full design.

## Conventions

- Commit messages in Japanese (unless English is requested)
- All commands are defined in `justfile` — run `just --list` to see available tasks
- Required environment variables are listed in `.env.example`

## Security

- Never commit secrets — gitleaks runs on every commit via lefthook (`gitleaks git --staged`)
- Use environment variables or GCP Secret Manager for credentials
- `.env` files are gitignored and must not be committed
- Internal API endpoints (`/tasks/*`, `/commands/*`) authenticate via `AGENT_API_TOKEN`
  or Cloud Tasks/Scheduler OIDC service account identity — see `api/main.py`
- Discord Interactions endpoint verifies Ed25519 request signatures — see `minutes_agent/discord.py`

## Testing

```bash
just test            # pytest + unittest discover
just check           # lint + typecheck + test — full local check (CI wiring is a follow-up)
```
