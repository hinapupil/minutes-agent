from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, cast

from minutes_agent.config import Settings


class AgentApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.normalized_agent_api_base_url}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = self._headers(url)
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                data = response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"Agent API returned HTTP {exc.code}: {exc.read()!r}") from exc
        if not data:
            return {}
        return cast(dict[str, Any], json.loads(data.decode("utf-8")))

    def _headers(self, audience: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._settings.agent_api_token:
            headers["X-Agent-Token"] = self._settings.agent_api_token
        if self._settings.agent_api_use_oidc:
            headers["Authorization"] = f"Bearer {self._fetch_identity_token(audience)}"
        return headers

    def _fetch_identity_token(self, audience: str) -> str:
        from google.auth.transport.requests import Request
        from google.oauth2.id_token import fetch_id_token

        return str(fetch_id_token(Request(), audience))
