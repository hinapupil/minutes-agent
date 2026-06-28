from __future__ import annotations

import json
import urllib.request
from typing import Any, cast

from minutes_agent.config import Settings


class AgentApiClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._settings.normalized_agent_api_base_url}{path}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._settings.agent_api_token:
            headers["X-Agent-Token"] = self._settings.agent_api_token
        request = urllib.request.Request(url, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(request, timeout=60) as response:
            data = response.read()
            if response.status >= 400:
                raise RuntimeError(f"Agent API returned HTTP {response.status}: {data!r}")
            if not data:
                return {}
            return cast(dict[str, Any], json.loads(data.decode("utf-8")))
