from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from bot.commands.recording import _human_members, _should_offer_recording_prompt


class RecordingPromptTest(unittest.TestCase):
    def test_human_members_excludes_bots(self) -> None:
        channel = SimpleNamespace(
            members=[
                SimpleNamespace(bot=False),
                SimpleNamespace(bot=True),
                SimpleNamespace(bot=False),
            ]
        )

        self.assertEqual(len(_human_members(channel)), 2)

    def test_should_offer_on_first_human_join(self) -> None:
        member = SimpleNamespace(bot=False)
        channel = SimpleNamespace(id=1, members=[member])
        before = SimpleNamespace(channel=None)
        after = SimpleNamespace(channel=channel)

        self.assertTrue(
            _should_offer_recording_prompt(
                member,
                before,
                after,
                is_active=False,
                last_prompted_at=None,
                now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
            )
        )

    def test_should_not_offer_when_second_human_joins(self) -> None:
        member = SimpleNamespace(bot=False)
        other = SimpleNamespace(bot=False)
        channel = SimpleNamespace(id=1, members=[other, member])

        self.assertFalse(
            _should_offer_recording_prompt(
                member,
                SimpleNamespace(channel=None),
                SimpleNamespace(channel=channel),
                is_active=False,
                last_prompted_at=None,
                now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
            )
        )

    def test_should_not_offer_when_recording_is_active(self) -> None:
        member = SimpleNamespace(bot=False)
        channel = SimpleNamespace(id=1, members=[member])

        self.assertFalse(
            _should_offer_recording_prompt(
                member,
                SimpleNamespace(channel=None),
                SimpleNamespace(channel=channel),
                is_active=True,
                last_prompted_at=None,
                now=datetime(2026, 7, 9, 12, 0, tzinfo=UTC),
            )
        )

    def test_should_not_offer_during_cooldown(self) -> None:
        member = SimpleNamespace(bot=False)
        channel = SimpleNamespace(id=1, members=[member])
        now = datetime(2026, 7, 9, 12, 0, tzinfo=UTC)

        self.assertFalse(
            _should_offer_recording_prompt(
                member,
                SimpleNamespace(channel=None),
                SimpleNamespace(channel=channel),
                is_active=False,
                last_prompted_at=now - timedelta(minutes=4),
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
