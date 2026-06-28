from __future__ import annotations

from minutes_agent.config import get_settings
from minutes_agent.firestore import FirestoreRepository


def search_minutes(query: str, limit: int = 5) -> list[dict[str, object]]:
    settings = get_settings()
    repository = FirestoreRepository(settings)
    return [meeting.model_dump(mode="json") for meeting in repository.search_minutes(query, limit)]


def get_pending_actions(limit: int = 100) -> list[dict[str, object]]:
    settings = get_settings()
    repository = FirestoreRepository(settings)
    return [item.model_dump(mode="json") for item in repository.list_pending_actions(limit)]

