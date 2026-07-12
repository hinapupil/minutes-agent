from __future__ import annotations

import io
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from starlette.requests import Request

from api.interactions import _download_attachment, _safe_attachment_filename
from api.main import (
    _oidc_audience_for_request,
    _route_allowed,
    _verify_agent_token,
    _verify_internal_request,
)
from minutes_agent.api_client import AgentApiClient
from minutes_agent.config import Settings
from minutes_agent.discord import DiscordNotifier
from minutes_agent.models import ActionItem, MeetingRecord
from minutes_agent.tasks import CloudTasksPublisher


def _request(path: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "https",
            "server": ("internal.example.run.app", 443),
            "path": path,
            "headers": [(b"host", b"internal.example.run.app")],
            "query_string": b"",
        }
    )


class FakeHttpMethod:
    POST = "POST"


class FakeTasksV2:
    HttpMethod = FakeHttpMethod


class FakeTasksClient:
    def __init__(self) -> None:
        self.created_task: dict[str, object] | None = None

    def queue_path(self, project: str, location: str, queue: str) -> str:
        return f"projects/{project}/locations/{location}/queues/{queue}"

    def create_task(self, request: dict[str, object]) -> SimpleNamespace:
        self.created_task = request["task"]  # type: ignore[assignment]
        return SimpleNamespace(name="task-name")


class FakeDownloadResponse:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self._data = io.BytesIO(data)
        self.headers = headers or {}

    def __enter__(self) -> FakeDownloadResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        return self._data.read(size)


class PrReviewFixesTest(unittest.TestCase):
    def test_agent_token_missing_fails_secure(self) -> None:
        with self.assertRaises(HTTPException) as context:
            _verify_agent_token(None, None)

        self.assertEqual(context.exception.status_code, 503)

    def test_internal_request_without_any_auth_configuration_fails_secure(self) -> None:
        settings = Settings(agent_api_token=None, cloud_tasks_service_account_email=None)

        with self.assertRaises(HTTPException) as context:
            _verify_internal_request(settings, None, None, _request("/tasks/check-actions"))

        self.assertEqual(context.exception.status_code, 503)

    def test_oidc_audience_includes_request_path(self) -> None:
        settings = Settings(cloud_run_base_url="https://internal.example.run.app/")

        audience = _oidc_audience_for_request(settings, _request("/tasks/generate-minutes"))

        self.assertEqual(audience, "https://internal.example.run.app/tasks/generate-minutes")

    def test_route_profiles_split_public_and_internal_paths(self) -> None:
        self.assertTrue(_route_allowed(Settings(route_profile="public"), "/"))
        self.assertFalse(_route_allowed(Settings(route_profile="internal"), "/"))
        self.assertTrue(_route_allowed(Settings(route_profile="public"), "/interactions"))
        self.assertFalse(_route_allowed(Settings(route_profile="public"), "/tasks/check-actions"))
        self.assertTrue(_route_allowed(Settings(route_profile="internal"), "/commands/ask"))
        self.assertFalse(_route_allowed(Settings(route_profile="internal"), "/interactions"))

    def test_cloud_tasks_oidc_audience_matches_task_url(self) -> None:
        settings = Settings(
            google_cloud_project="project",
            cloud_run_base_url="https://internal.example.run.app",
            cloud_tasks_service_account_email="agent@example.iam.gserviceaccount.com",
        )
        client = FakeTasksClient()
        publisher = CloudTasksPublisher.__new__(CloudTasksPublisher)
        publisher._settings = settings
        publisher._tasks_v2 = FakeTasksV2
        publisher._client = client

        publisher._enqueue_http_task("https://internal.example.run.app/tasks/check-actions", b"{}")

        assert client.created_task is not None
        http_request = client.created_task["http_request"]  # type: ignore[index]
        oidc_token = http_request["oidc_token"]  # type: ignore[index]
        self.assertEqual(
            oidc_token["audience"],  # type: ignore[index]
            "https://internal.example.run.app/tasks/check-actions",
        )

    def test_agent_api_client_adds_oidc_header_when_enabled(self) -> None:
        client = AgentApiClient(
            Settings(agent_api_base_url="https://internal.example.run.app", agent_api_use_oidc=True)
        )

        with patch.object(client, "_fetch_identity_token", return_value="id-token"):
            headers = client._headers("https://internal.example.run.app/commands/ask")

        self.assertEqual(headers["Authorization"], "Bearer id-token")

    def test_agent_api_client_http_error_includes_response_body(self) -> None:
        error = urllib.error.HTTPError(
            "https://internal.example.run.app/commands/ask",
            400,
            "Bad Request",
            {},
            io.BytesIO(b"bad payload"),
        )
        client = AgentApiClient(Settings(agent_api_base_url="https://internal.example.run.app"))

        with (
            patch("minutes_agent.api_client.urllib.request.urlopen", side_effect=error),
            self.assertRaises(RuntimeError) as context,
        ):
            client.post("/commands/ask", {"question": "q"})

        self.assertIn("bad payload", str(context.exception))

    def test_discord_minutes_content_is_limited_to_webhook_limit(self) -> None:
        notifier = DiscordNotifier(Settings())
        meeting = MeetingRecord(
            meeting_id="m" * 32,
            guild_id="g1",
            channel_id="c1",
            minutes_md="あ" * 1900,
        )
        action_items = [
            ActionItem(meeting_id=meeting.meeting_id, title=f"todo-{index}" * 20)
            for index in range(10)
        ]

        content = notifier._build_minutes_content(meeting, action_items)

        self.assertLessEqual(len(content), 2000)

    def test_discord_http_error_includes_response_body(self) -> None:
        error = urllib.error.HTTPError(
            "https://discord.example/webhook",
            400,
            "Bad Request",
            {},
            io.BytesIO(b"too long"),
        )
        notifier = DiscordNotifier(Settings())

        with (
            patch("minutes_agent.discord.urllib.request.urlopen", side_effect=error),
            self.assertRaises(RuntimeError) as context,
        ):
            notifier._post_json("https://discord.example/webhook", {"content": "x"})

        self.assertIn("too long", str(context.exception))

    def test_attachment_filename_uses_basename_only(self) -> None:
        self.assertEqual(_safe_attachment_filename("../audio.wav"), "audio.wav")
        self.assertEqual(_safe_attachment_filename("C:\\tmp\\audio.wav"), "audio.wav")
        self.assertEqual(_safe_attachment_filename(""), "attachment")

    def test_attachment_download_has_size_limit(self) -> None:
        response = FakeDownloadResponse(b"abcdef", {"Content-Length": "6"})

        with (
            patch("api.interactions.urllib.request.urlopen", return_value=response),
            self.assertRaises(ValueError),
        ):
            _download_attachment(
                "https://cdn.discordapp.example/audio.wav",
                Path("unused.wav"),
                max_bytes=5,
            )


if __name__ == "__main__":
    unittest.main()
