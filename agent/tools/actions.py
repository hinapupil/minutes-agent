from __future__ import annotations

from datetime import datetime
from typing import Any

from agent.tools.gemini_client import GeminiTextClient
from minutes_agent.config import Settings
from minutes_agent.json_utils import ensure_list, extract_json_payload
from minutes_agent.models import ActionItem

ACTION_PROMPT_TEMPLATE = """\
あなたは議事録から Action Item を抽出するエージェントです。

制約:
- JSON のみを出力する
- 推測で担当者や期限を補完しない
- 担当者が不明なら assignee は null
- 期限が不明なら due_date は null
- due_date は分かる場合だけ ISO 8601 形式にする
- title は命令形または実行可能な作業名にする

JSON schema:
[
  {{
    "title": "string",
    "description": "string",
    "assignee": "string|null",
    "assignee_id": "string|null",
    "due_date": "ISO8601|null",
    "source_quote": "string|null"
  }}
]

議事録:
{minutes_md}

文字起こし:
{transcript}
"""


class ActionExtractor:
    def __init__(self, settings: Settings) -> None:
        self._client = GeminiTextClient(settings)

    def extract(self, meeting_id: str, minutes_md: str, transcript: str = "") -> list[ActionItem]:
        if not minutes_md.strip():
            return []
        prompt = ACTION_PROMPT_TEMPLATE.format(
            minutes_md=minutes_md.strip(),
            transcript=transcript.strip() or "なし",
        )
        response = self._client.generate(prompt)
        payload = ensure_list(extract_json_payload(response))
        items: list[ActionItem] = []
        for raw in payload:
            if not isinstance(raw, dict):
                continue
            item = self._to_action_item(meeting_id, raw)
            if item is not None:
                items.append(item)
        return items

    def _to_action_item(self, meeting_id: str, raw: dict[str, Any]) -> ActionItem | None:
        title = str(raw.get("title") or "").strip()
        if not title:
            return None
        due_date = _parse_datetime(raw.get("due_date"))
        return ActionItem(
            meeting_id=meeting_id,
            title=title,
            description=str(raw.get("description") or "").strip(),
            assignee=_nullable_string(raw.get("assignee")),
            assignee_id=_nullable_string(raw.get("assignee_id")),
            due_date=due_date,
            source_quote=_nullable_string(raw.get("source_quote")),
        )


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None

