from __future__ import annotations

import unittest
from datetime import UTC, datetime
from typing import Any

from minutes_agent.models import MeetingRecord, TextMessage, TranscriptSegment
from minutes_agent.workflow import MinutesWorkflow


class FakeQuestionAnswerer:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def answer(
        self,
        question: str,
        *,
        limit: int = 5,
        user_id: str = "minutes-agent",
        session_id: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "question": question,
                "limit": limit,
                "user_id": user_id,
                "session_id": session_id,
            }
        )
        return "Runner 経由の回答"


class FakeGuildSettingsRepository:
    def __init__(self, guild_settings: dict[str, Any] | None) -> None:
        self._guild_settings = guild_settings

    def list_recent_minutes(self, before: datetime, limit: int = 5) -> list[Any]:
        return []

    def get_guild_settings(self, guild_id: str) -> dict[str, Any] | None:
        return self._guild_settings


class WorkflowTest(unittest.TestCase):
    def test_build_context_injects_glossary_when_configured(self) -> None:
        workflow = MinutesWorkflow.__new__(MinutesWorkflow)
        workflow._repository = FakeGuildSettingsRepository(
            {"repo": "hinapupil/minutes-agent", "glossary": ["MiyaIF", "Proto Pedia"]}
        )
        meeting = MeetingRecord(meeting_id="m1", guild_id="g1", channel_id="c1")

        context = workflow._build_context(meeting)

        self.assertIn("## プロジェクト用語集", context)
        self.assertIn("MiyaIF", context)
        self.assertIn("Proto Pedia", context)

    def test_build_context_omits_glossary_block_when_not_configured(self) -> None:
        workflow = MinutesWorkflow.__new__(MinutesWorkflow)
        workflow._repository = FakeGuildSettingsRepository(None)
        meeting = MeetingRecord(meeting_id="m1", guild_id="g1", channel_id="c1")

        context = workflow._build_context(meeting)

        self.assertEqual(context, "")

    def test_build_context_falls_back_when_guild_settings_read_fails(self) -> None:
        class BrokenRepository(FakeGuildSettingsRepository):
            def get_guild_settings(self, guild_id: str) -> dict[str, Any] | None:
                raise RuntimeError("firestore unavailable")

        workflow = MinutesWorkflow.__new__(MinutesWorkflow)
        workflow._repository = BrokenRepository(None)
        meeting = MeetingRecord(meeting_id="m1", guild_id="g1", channel_id="c1")

        context = workflow._build_context(meeting)

        self.assertEqual(context, "")


    def test_full_transcript_includes_text_channel_messages(self) -> None:
        workflow = MinutesWorkflow.__new__(MinutesWorkflow)
        meeting = MeetingRecord(
            meeting_id="m1",
            guild_id="g1",
            channel_id="c1",
            text_messages=[
                TextMessage(
                    message_id="msg1",
                    author_id="u2",
                    author_name="Bob",
                    content="テキストで補足します",
                    created_at=datetime(2026, 6, 28, 3, 0, tzinfo=UTC),
                )
            ],
        )
        transcript = workflow._render_full_transcript(
            meeting,
            [
                TranscriptSegment(
                    speaker_id="u1",
                    speaker_name="Alice",
                    text="音声発言です",
                )
            ],
        )

        self.assertIn("Alice: 音声発言です", transcript)
        self.assertIn("# テキストチャンネル発言", transcript)
        self.assertIn("Bob: テキストで補足します", transcript)

    def test_answer_question_delegates_to_question_answerer(self) -> None:
        answerer = FakeQuestionAnswerer()
        workflow = MinutesWorkflow.__new__(MinutesWorkflow)
        workflow._question_answerer = answerer

        answer = workflow.answer_question(
            "前回の決定事項は？",
            limit=3,
            user_id="discord-guild:g1",
            session_id="ask:g1:c1",
        )

        self.assertEqual(answer, "Runner 経由の回答")
        self.assertEqual(
            answerer.calls,
            [
                {
                    "question": "前回の決定事項は？",
                    "limit": 3,
                    "user_id": "discord-guild:g1",
                    "session_id": "ask:g1:c1",
                }
            ],
        )


class FakeRunner:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def run(self, *, user_id: str, session_id: str, new_message: object) -> list[dict[str, Any]]:
        self.calls.append(
            {"user_id": user_id, "session_id": session_id, "new_message": new_message}
        )
        return [
            {
                "final": True,
                "content": {"parts": [{"text": "前回はリリース日程を確認しました"}]},
            }
        ]


class AdkRuntimeTest(unittest.TestCase):
    def test_question_answerer_runs_adk_runner(self) -> None:
        from agent.runtime import AdkQuestionAnswerer
        from minutes_agent.config import Settings

        runner = FakeRunner()
        answerer = AdkQuestionAnswerer(
            Settings(),
            runner=runner,
            content_factory=lambda text: {"content": text},
        )

        answer = answerer.answer(
            "前回のリリース日程は？",
            limit=3,
            user_id="discord-guild:g1",
            session_id="ask:g1:c1",
        )

        self.assertEqual(answer, "前回はリリース日程を確認しました")
        self.assertEqual(runner.calls[0]["user_id"], "discord-guild:g1")
        self.assertEqual(runner.calls[0]["session_id"], "ask:g1:c1")
        prompt = runner.calls[0]["new_message"]["content"]
        self.assertIn("search_minutes", prompt)
        self.assertIn("get_pending_actions", prompt)
        self.assertIn("検索上限: 3", prompt)


if __name__ == "__main__":
    unittest.main()
