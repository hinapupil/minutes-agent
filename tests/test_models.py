from __future__ import annotations

import unittest

from minutes_agent.models import MeetingRecord, TranscriptSegment


class ModelsTest(unittest.TestCase):
    def test_render_transcript_uses_segments_when_text_is_empty(self) -> None:
        meeting = MeetingRecord(
            meeting_id="m1",
            guild_id="g1",
            channel_id="c1",
            transcript_segments=[
                TranscriptSegment(
                    speaker_id="u1",
                    speaker_name="Alice",
                    text="次回までにAPIを確認します",
                    start_seconds=1.2,
                )
            ],
        )
        self.assertIn("Alice", meeting.render_transcript())
        self.assertIn("API", meeting.render_transcript())

    def test_blank_transcript_segment_is_invalid(self) -> None:
        with self.assertRaises(ValueError):
            TranscriptSegment(speaker_id="u1", text=" ")


if __name__ == "__main__":
    unittest.main()

