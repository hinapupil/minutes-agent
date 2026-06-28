from __future__ import annotations

import unittest
from dataclasses import dataclass

from agent.tools.transcribe import _segments_from_diarized_words


@dataclass(slots=True)
class Word:
    word: str
    speaker_label: str
    start_offset: object | None = None
    end_offset: object | None = None


class TranscribeTest(unittest.TestCase):
    def test_groups_contiguous_words_by_speaker_label(self) -> None:
        segments = _segments_from_diarized_words(
            [
                Word("A", "speaker_1"),
                Word("B", "speaker_1"),
                Word("C", "speaker_2"),
            ],
            speaker_id="manual",
            speaker_name="upload",
        )

        self.assertEqual([segment.speaker_id for segment in segments], [
            "manual:speaker_1",
            "manual:speaker_2",
        ])
        self.assertEqual(segments[0].text, "A B")
        self.assertEqual(segments[1].text, "C")


if __name__ == "__main__":
    unittest.main()

