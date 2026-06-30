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
    ruff check .

# Run type checks
typecheck:
    mypy minutes_agent api agent bot

# Run tests
test:
    pytest
    python -m unittest discover -s tests

# Format code
fmt:
    ruff format .

# Check all (lint + typecheck + test) — used by CI
check: lint typecheck test
