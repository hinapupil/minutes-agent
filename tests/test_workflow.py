from __future__ import annotations

import unittest
from datetime import UTC, datetime

from minutes_agent.models import MeetingRecord, TextMessage, TranscriptSegment
from minutes_agent.workflow import MinutesWorkflow


class WorkflowTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

