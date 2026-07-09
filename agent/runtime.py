from __future__ import annotations

from typing import Any

from agent.agent import root_agent
from minutes_agent.config import Settings, get_settings


def build_firestore_services(settings: Settings | None = None) -> tuple[Any, Any]:
    actual_settings = settings or get_settings()
    actual_settings.require("google_cloud_project")

    from google.adk.integrations.firestore.firestore_memory_service import (
        FirestoreMemoryService,
    )
    from google.adk.integrations.firestore.firestore_session_service import (
        FirestoreSessionService,
    )
    from google.cloud import firestore

    client = firestore.AsyncClient(project=actual_settings.google_cloud_project)
    session_service = FirestoreSessionService(client=client, root_collection="adk-session")
    memory_service = FirestoreMemoryService(
        client=client,
        events_collection="events",
        memories_collection="memories",
    )
    return session_service, memory_service


def build_runner(settings: Settings | None = None) -> Any:
    from google.adk.runners import Runner

    session_service, memory_service = build_firestore_services(settings)
    return Runner(
        app_name="minutes-agent",
        agent=root_agent,
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )

