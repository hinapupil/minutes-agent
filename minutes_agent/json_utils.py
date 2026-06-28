from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any


def extract_json_payload(text: str) -> Any:
    """Extract the first JSON object or array from an LLM response."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    decoder = json.JSONDecoder()
    for index, character in enumerate(stripped):
        if character not in "[{":
            continue
        try:
            payload, _ = decoder.raw_decode(stripped[index:])
        except json.JSONDecodeError:
            continue
        return payload
    raise ValueError("JSON payload was not found")


def ensure_list(payload: Any) -> list[Any]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "actions", "action_items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    if isinstance(payload, Sequence) and not isinstance(payload, str):
        return list(payload)
    raise TypeError(f"Expected list-like JSON payload, got {type(payload).__name__}")

