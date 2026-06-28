from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value


def _env_list(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    value = _env(name)
    if value is None:
        return default
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True, slots=True)
class Settings:
    discord_bot_token: str | None = field(default_factory=lambda: _env("DISCORD_BOT_TOKEN"))
    discord_application_id: str | None = field(
        default_factory=lambda: _env("DISCORD_APPLICATION_ID")
    )
    discord_public_key: str | None = field(default_factory=lambda: _env("DISCORD_PUBLIC_KEY"))
    discord_channel_id: str | None = field(default_factory=lambda: _env("DISCORD_CHANNEL_ID"))
    discord_guild_id: str | None = field(default_factory=lambda: _env("DISCORD_GUILD_ID"))
    discord_webhook_url: str | None = field(default_factory=lambda: _env("DISCORD_WEBHOOK_URL"))

    google_cloud_project: str | None = field(default_factory=lambda: _env("GOOGLE_CLOUD_PROJECT"))
    google_cloud_location: str = field(
        default_factory=lambda: (
            _env("GOOGLE_CLOUD_LOCATION", "asia-northeast1") or "asia-northeast1"
        )
    )
    gcs_bucket_name: str | None = field(default_factory=lambda: _env("GCS_BUCKET_NAME"))
    cloud_tasks_queue: str = field(
        default_factory=lambda: _env("CLOUD_TASKS_QUEUE", "minutes-agent") or "minutes-agent"
    )
    cloud_run_base_url: str | None = field(default_factory=lambda: _env("CLOUD_RUN_BASE_URL"))
    cloud_tasks_service_account_email: str | None = field(
        default_factory=lambda: _env("CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL")
    )

    gemini_model: str = field(
        default_factory=lambda: _env("GEMINI_MODEL", "gemini-3.5-flash") or "gemini-3.5-flash"
    )
    gemini_api_key: str | None = field(default_factory=lambda: _env("GEMINI_API_KEY"))
    speech_model: str = field(default_factory=lambda: _env("SPEECH_MODEL", "chirp_2") or "chirp_2")
    speech_language_codes: tuple[str, ...] = field(
        default_factory=lambda: _env_list("SPEECH_LANGUAGE_CODES", ("ja-JP",))
    )
    speech_batch_timeout_seconds: int = field(
        default_factory=lambda: int(_env("SPEECH_BATCH_TIMEOUT_SECONDS", "1800") or "1800")
    )
    speech_enable_diarization: bool = field(
        default_factory=lambda: (_env("SPEECH_ENABLE_DIARIZATION", "true") or "true").lower()
        in {"1", "true", "yes", "on"}
    )
    speech_min_speaker_count: int = field(
        default_factory=lambda: int(_env("SPEECH_MIN_SPEAKER_COUNT", "1") or "1")
    )
    speech_max_speaker_count: int = field(
        default_factory=lambda: int(_env("SPEECH_MAX_SPEAKER_COUNT", "8") or "8")
    )

    agent_api_base_url: str = field(
        default_factory=lambda: _env("AGENT_API_BASE_URL", "http://localhost:8080")
        or "http://localhost:8080"
    )
    agent_api_token: str | None = field(default_factory=lambda: _env("AGENT_API_TOKEN"))
    local_recordings_dir: Path = field(
        default_factory=lambda: Path(
            _env("LOCAL_RECORDINGS_DIR", "data/recordings") or "data/recordings"
        )
    )

    def require(self, *names: str) -> None:
        missing = [name for name in names if getattr(self, name) in (None, "")]
        if missing:
            joined = ", ".join(missing)
            raise RuntimeError(f"Missing required settings: {joined}")

    @property
    def normalized_agent_api_base_url(self) -> str:
        return self.agent_api_base_url.rstrip("/")

    @property
    def normalized_cloud_run_base_url(self) -> str:
        if not self.cloud_run_base_url:
            raise RuntimeError("Missing required setting: cloud_run_base_url")
        return self.cloud_run_base_url.rstrip("/")

    @property
    def recognizer_path(self) -> str:
        self.require("google_cloud_project")
        return (
            f"projects/{self.google_cloud_project}/locations/"
            f"{self.google_cloud_location}/recognizers/_"
        )


def get_settings() -> Settings:
    return Settings()
