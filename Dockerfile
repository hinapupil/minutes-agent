FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt pyproject.toml README.md ./
RUN pip install --no-cache-dir -r requirements.txt

COPY agent ./agent
COPY api ./api
COPY minutes_agent ./minutes_agent

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]

