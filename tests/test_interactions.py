from __future__ import annotations

import unittest
from typing import Any
from unittest.mock import patch

from minutes_agent.config import Settings


class RunSetupFollowupTest(unittest.TestCase):
    def test_success_saves_glossary_and_sends_public_followup(self) -> None:
        from api import interactions

        saved: dict[str, Any] = {}
        sent: list[dict[str, Any]] = []

        class _FakeRepository:
            def __init__(self, settings: Settings) -> None:
                pass

            def save_guild_settings(self, guild_id: str, data: dict[str, Any]) -> None:
                saved["guild_id"] = guild_id
                saved["data"] = data

        class _FakeNotifier:
            def __init__(self, settings: Settings) -> None:
                pass

            def send_interaction_followup(
                self,
                application_id: str,
                token: str,
                content: str,
                *,
                ephemeral: bool = False,
            ) -> None:
                sent.append(
                    {
                        "application_id": application_id,
                        "token": token,
                        "content": content,
                        "ephemeral": ephemeral,
                    }
                )

        with (
            patch.object(
                interactions,
                "fetch_repo_glossary",
                return_value=["MiyaIF", "Proto Pedia"],
            ),
            patch.object(interactions, "FirestoreRepository", _FakeRepository),
            patch.object(interactions, "DiscordNotifier", _FakeNotifier),
        ):
            interactions._run_setup_followup(
                Settings(),
                "app-id",
                "token-value",
                "guild-1",
                "hinapupil/minutes-agent",
            )

        self.assertEqual(saved["guild_id"], "guild-1")
        self.assertEqual(saved["data"]["repo"], "hinapupil/minutes-agent")
        self.assertEqual(saved["data"]["glossary"], ["MiyaIF", "Proto Pedia"])
        self.assertIn("glossary_updated_at", saved["data"])

        self.assertEqual(len(sent), 1)
        self.assertFalse(sent[0]["ephemeral"])
        self.assertIn("2語", sent[0]["content"])
        self.assertIn("MiyaIF", sent[0]["content"])

    def test_failure_sends_ephemeral_followup_without_traceback(self) -> None:
        from api import interactions

        sent: list[dict[str, Any]] = []

        class _FakeNotifier:
            def __init__(self, settings: Settings) -> None:
                pass

            def send_interaction_followup(
                self,
                application_id: str,
                token: str,
                content: str,
                *,
                ephemeral: bool = False,
            ) -> None:
                sent.append({"content": content, "ephemeral": ephemeral})

        with (
            patch.object(
                interactions,
                "fetch_repo_glossary",
                side_effect=ValueError("リポジトリ owner/repo が見つかりません"),
            ),
            patch.object(interactions, "DiscordNotifier", _FakeNotifier),
        ):
            interactions._run_setup_followup(
                Settings(),
                "app-id",
                "token-value",
                "guild-1",
                "owner/repo",
            )

        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0]["ephemeral"])
        self.assertIn("失敗", sent[0]["content"])
        self.assertNotIn("Traceback", sent[0]["content"])


class SetupCommandValidationTest(unittest.TestCase):
    def test_repo_slug_pattern_rejects_malformed_input(self) -> None:
        from minutes_agent.github_glossary import REPO_SLUG_PATTERN

        self.assertIsNone(REPO_SLUG_PATTERN.match("not-a-valid-repo"))
        self.assertIsNotNone(REPO_SLUG_PATTERN.match("hinapupil/minutes-agent"))


if __name__ == "__main__":
    unittest.main()
