from __future__ import annotations

from pathlib import Path
from typing import cast

from minutes_agent.config import Settings


class GcsStorage:
    def __init__(self, settings: Settings) -> None:
        settings.require("gcs_bucket_name")
        from google.cloud import storage  # type: ignore[attr-defined]

        self._settings = settings
        self._client = storage.Client(project=settings.google_cloud_project)
        self._bucket = self._client.bucket(cast(str, settings.gcs_bucket_name))

    def upload_file(self, local_path: Path, object_name: str, content_type: str) -> str:
        blob = self._bucket.blob(object_name)
        blob.upload_from_filename(str(local_path), content_type=content_type)
        return f"gs://{self._bucket.name}/{object_name}"

    def upload_audio_file(self, local_path: Path, meeting_id: str, speaker_id: str) -> str:
        object_name = f"meetings/{meeting_id}/audio/{speaker_id}.wav"
        return self.upload_file(local_path, object_name, "audio/wav")
