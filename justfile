# Project tasks — run `just --list` to see all available commands
# Lint/typecheck/test recipes assume the app code from PR #1
# (Bot/API/Agent実装とインフラ定義を追加) is present — pyproject.toml,
# minutes_agent/, api/, agent/, bot/, tests/.

# Install dependencies and set up git hooks
setup:
    pip install -e ".[dev]"
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

# Check all (lint + typecheck + test) — used by CI
check: lint typecheck test
