from __future__ import annotations

import json
from typing import cast

from minutes_agent.config import Settings
from minutes_agent.models import GenerateMinutesRequest


class CloudTasksPublisher:
    def __init__(self, settings: Settings, *, target_base_url: str | None = None) -> None:
        settings.require("google_cloud_project")
        from google.cloud import tasks_v2

        self._tasks_v2 = tasks_v2
        self._settings = settings
        self._client = tasks_v2.CloudTasksClient()
        self._target_base_url = (target_base_url or settings.cloud_run_base_url or "").rstrip("/")
        if not self._target_base_url:
            raise RuntimeError("Missing required setting: cloud_run_base_url")

    def enqueue_generate_minutes(self, request: GenerateMinutesRequest) -> str:
        url = f"{self._target_base_url}/tasks/generate-minutes"
        payload = request.model_dump_json().encode("utf-8")
        return self._enqueue_http_task(url, payload)

    def enqueue_check_actions(self) -> str:
        url = f"{self._target_base_url}/tasks/check-actions"
        return self._enqueue_http_task(url, b"{}")

    def _enqueue_http_task(self, url: str, body: bytes) -> str:
        project = cast(str, self._settings.google_cloud_project)
        parent = self._client.queue_path(
            project,
            self._settings.google_cloud_location,
            self._settings.cloud_tasks_queue,
        )
        http_request: dict[str, object] = {
            "http_method": self._tasks_v2.HttpMethod.POST,
            "url": url,
            "headers": {"Content-Type": "application/json"},
            "body": body,
        }
        if self._settings.cloud_tasks_service_account_email:
            http_request["oidc_token"] = {
                "service_account_email": self._settings.cloud_tasks_service_account_email,
                "audience": url,
            }
        if self._settings.agent_api_token:
            http_request["headers"] = {
                "Content-Type": "application/json",
                "X-Agent-Token": self._settings.agent_api_token,
            }
        task = {"http_request": http_request}
        response = self._client.create_task(request={"parent": parent, "task": task})
        return response.name


def encode_json(data: dict[str, object]) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
