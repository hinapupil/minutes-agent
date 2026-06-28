from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass
from typing import Any

from minutes_agent.config import Settings
from minutes_agent.models import ActionItem, MeetingRecord


def verify_discord_signature(public_key: str, timestamp: str, signature: str, body: bytes) -> bool:
    from nacl.exceptions import BadSignatureError
    from nacl.signing import VerifyKey

    try:
        verify_key = VerifyKey(bytes.fromhex(public_key))
        verify_key.verify(timestamp.encode("utf-8") + body, bytes.fromhex(signature))
    except (BadSignatureError, ValueError):
        return False
    return True


@dataclass(slots=True)
class DiscordNotifier:
    settings: Settings

    def post_minutes(
        self,
        meeting: MeetingRecord,
        action_items: list[ActionItem],
        webhook_url: str | None = None,
    ) -> bool:
        url = webhook_url or self.settings.discord_webhook_url
        if not url:
            return False
        content = self._build_minutes_content(meeting, action_items)
        self._post_json(url, {"content": content})
        return True

    def post_action_reminder(self, action_items: list[ActionItem]) -> bool:
        if not action_items or not self.settings.discord_webhook_url:
            return False
        lines = ["未完了のアクションアイテムがあります"]
        for item in action_items:
            due = item.due_date.date().isoformat() if item.due_date else "期限未設定"
            assignee = item.assignee or "担当者未設定"
            lines.append(f"- `{item.action_id}` {item.title} / {assignee} / {due}")
        self._post_json(self.settings.discord_webhook_url, {"content": "\n".join(lines)})
        return True

    def send_interaction_followup(
        self,
        application_id: str,
        token: str,
        content: str,
        *,
        ephemeral: bool = False,
    ) -> None:
        flags = 64 if ephemeral else 0
        url = f"https://discord.com/api/v10/webhooks/{application_id}/{token}"
        payload: dict[str, Any] = {"content": content}
        if flags:
            payload["flags"] = flags
        self._post_json(url, payload)

    def _build_minutes_content(self, meeting: MeetingRecord, action_items: list[ActionItem]) -> str:
        minutes = meeting.minutes_md or "議事録本文がありません"
        if len(minutes) > 1700:
            minutes = f"{minutes[:1700]}\n\n...省略"
        lines = [f"## 議事録 `{meeting.meeting_id}`", minutes]
        if action_items:
            lines.append("\n## アクションアイテム")
            for item in action_items:
                assignee = item.assignee or "担当者未設定"
                due = item.due_date.date().isoformat() if item.due_date else "期限未設定"
                lines.append(f"- `{item.action_id}` {item.title} / {assignee} / {due}")
        return "\n".join(lines)

    def _post_json(self, url: str, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                raise RuntimeError(f"Discord API returned HTTP {response.status}")

