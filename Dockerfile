FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# py-cord を upstream ブランチ (git+https) から入れるため git が必要 (#3159 先取り)
RUN apt-get update \
  && apt-get install -y --no-install-recommends git \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent
COPY api ./api
COPY minutes_agent ./minutes_agent

# Cloud Run のプロキシ配下で X-Forwarded-Proto を信頼させる（OIDC audience の
# https スキーム解決に必要。無いと /tasks/check-actions の署名検証が 401 になる）
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]

