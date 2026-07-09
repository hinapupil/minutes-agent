from __future__ import annotations

import asyncio
import inspect
from collections.abc import Awaitable, Callable
from typing import Any, cast

from minutes_agent.config import Settings, get_settings

RunnerFactory = Callable[[Settings | None], Any]
ContentFactory = Callable[[str], Any]


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

    from agent.agent import build_root_agent

    session_service, memory_service = build_firestore_services(settings)
    return Runner(
        app_name="minutes-agent",
        agent=build_root_agent(settings),
        session_service=session_service,
        memory_service=memory_service,
        auto_create_session=True,
    )


class AdkQuestionAnswerer:
    def __init__(
        self,
        settings: Settings,
        *,
        runner: Any | None = None,
        runner_factory: RunnerFactory = build_runner,
        content_factory: ContentFactory | None = None,
    ) -> None:
        self._settings = settings
        self._runner = runner
        self._runner_factory = runner_factory
        self._content_factory = content_factory or _content_from_text

    def answer(
        self,
        question: str,
        *,
        limit: int = 5,
        user_id: str = "minutes-agent",
        session_id: str | None = None,
    ) -> str:
        runner = self._runner or self._runner_factory(self._settings)
        prompt = _build_question_prompt(question, limit)
        message = self._content_factory(prompt)
        events = _run_runner(
            runner,
            user_id=user_id,
            session_id=session_id or "ask",
            message=message,
        )
        return _extract_final_text(events)


def _build_question_prompt(question: str, limit: int) -> str:
    return (
        "ユーザーの質問に日本語で簡潔に回答してください。\n"
        "必要に応じて search_minutes(query, limit) と get_pending_actions(limit) を"
        "自律的に選択してください。\n"
        "回答は取得できた議事録またはアクションアイテムだけを根拠にしてください。\n"
        "根拠がない場合は「分かりません」と答えてください。\n"
        f"検索上限: {limit}\n\n"
        f"質問:\n{question}"
    )


def _content_from_text(text: str) -> Any:
    from google.genai import types

    return types.Content(role="user", parts=[types.Part(text=text)])


def _run_runner(
    runner: Any,
    *,
    user_id: str,
    session_id: str,
    message: Any,
) -> list[Any]:
    run = getattr(runner, "run", None)
    if callable(run):
        events = run(user_id=user_id, session_id=session_id, new_message=message)
    else:
        run_async = getattr(runner, "run_async", None)
        if not callable(run_async):
            raise RuntimeError("ADK runner does not expose run or run_async")
        events = run_async(user_id=user_id, session_id=session_id, new_message=message)
    return _resolve_events(events)


def _resolve_events(events: Any) -> list[Any]:
    if inspect.isawaitable(events):
        events = _run_awaitable(events)
    if hasattr(events, "__aiter__"):
        return cast(list[Any], _run_awaitable(_collect_async_events(events)))
    return list(events)


async def _collect_async_events(events: Any) -> list[Any]:
    collected: list[Any] = []
    async for event in events:
        collected.append(event)
    return collected


def _run_awaitable(awaitable: Awaitable[Any]) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(_await_result(awaitable))
    raise RuntimeError("ADK runner returned an async result while an event loop is running")


async def _await_result(awaitable: Awaitable[Any]) -> Any:
    return await awaitable


def _extract_final_text(events: list[Any]) -> str:
    fallback: str | None = None
    for event in events:
        text = _event_text(event)
        if text:
            fallback = text
        if _is_final_response(event) and text:
            return text
    if fallback:
        return fallback
    raise RuntimeError("ADK runner did not return a text response")


def _is_final_response(event: Any) -> bool:
    is_final_response = getattr(event, "is_final_response", None)
    if callable(is_final_response):
        return bool(is_final_response())
    if isinstance(event, dict):
        return bool(event.get("final") or event.get("is_final_response"))
    return False


def _event_text(event: Any) -> str | None:
    content = event.get("content") if isinstance(event, dict) else getattr(event, "content", None)
    if content is None:
        return None
    parts = content.get("parts") if isinstance(content, dict) else getattr(content, "parts", None)
    if not parts:
        return None
    texts = []
    for part in parts:
        text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
        if text:
            texts.append(str(text))
    return "\n".join(texts).strip() or None

