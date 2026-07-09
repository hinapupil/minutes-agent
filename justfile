# Project tasks — run `just --list` to see all available commands
# Lint/typecheck/test recipes assume the app code from PR #1
# (Bot/API/Agent実装とインフラ定義を追加) is present — pyproject.toml,
# minutes_agent/, api/, agent/, bot/, tests/.

# Install dependencies and set up git hooks
setup:
    @if [ -f pyproject.toml ]; then pip install -e ".[dev]"; else echo "pyproject.toml not found — skipping pip install until app code (PR #1) lands"; fi
    lefthook install

# Start the Cloud Run API locally
dev-api:
    uvicorn api.main:app --reload --port 8080

# Start the Discord bot locally
dev-bot:
    python -m bot.main

# Run linters
lint:
    @if [ -f pyproject.toml ]; then ruff check .; else echo "pyproject.toml not found — skipping lint until app code (PR #1) lands"; fi

# Run type checks
typecheck:
    @if [ -f pyproject.toml ]; then mypy minutes_agent api agent bot; else echo "pyproject.toml not found — skipping typecheck until app code (PR #1) lands"; fi

# Run tests
test:
    @if [ -f pyproject.toml ]; then pytest && python -m unittest discover -s tests; else echo "pyproject.toml not found — skipping tests until app code (PR #1) lands"; fi

# Format code
fmt:
    ruff format .

# Check all (lint + typecheck + test) — full local check
check: lint typecheck test

# --- Infra (GCP) ---
# シークレットの値は Secret Manager だけに置く（tfstate/GitHub Secrets に値を入れない）。
# Terraform はシークレット名(ID)のみ参照し、Cloud Run/GCE が実行時に読む。

gcp_project := "minutes-agent-hackathon"

# Store one secret in Secret Manager (hidden prompt — value never hits argv/history)
secret-set name:
    #!/usr/bin/env bash
    set -euo pipefail
    gcloud secrets describe "{{name}}" --project "{{gcp_project}}" >/dev/null 2>&1 \
      || gcloud secrets create "{{name}}" --project "{{gcp_project}}" --replication-policy=automatic
    read -r -s -p "{{name}} の値を入力（表示されません）: " value; echo
    if [ -z "$value" ]; then echo "空の値は登録しません（中断）"; exit 1; fi
    printf '%s' "$value" | gcloud secrets versions add "{{name}}" --project "{{gcp_project}}" --data-file=-
    echo "✓ {{name}} に新しいバージョンを登録しました"

# Generate agent-api-token (random 64 hex) and store it — no human input needed
secret-gen-agent-token:
    #!/usr/bin/env bash
    set -euo pipefail
    gcloud secrets describe agent-api-token --project "{{gcp_project}}" >/dev/null 2>&1 \
      || gcloud secrets create agent-api-token --project "{{gcp_project}}" --replication-policy=automatic
    openssl rand -hex 32 | tr -d '\n' \
      | gcloud secrets versions add agent-api-token --project "{{gcp_project}}" --data-file=-
    echo "✓ agent-api-token を自動生成して登録しました"

# Register all runtime secrets (gemini-api-key は Vertex AI/ADC 利用なら不要 — tfvars で secret_id を "" に)
secrets-init: (secret-set "discord-bot-token") (secret-set "discord-webhook-url") secret-gen-agent-token

# Terraform init (backend: gs://minutes-agent-hackathon-tfstate)
tf-init:
    terraform -chdir=infra init

# Terraform plan (apply は意図的にレシピ化しない — 実行前に個別確認する運用)
tf-plan:
    terraform -chdir=infra plan
