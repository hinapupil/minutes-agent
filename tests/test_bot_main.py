from __future__ import annotations

import unittest

from bot.main import create_bot
from minutes_agent.config import Settings


class BotMainTest(unittest.TestCase):
    def test_create_bot_enables_required_gateway_intents(self) -> None:
        bot = create_bot(Settings())

        self.assertTrue(bot.intents.guilds)
        self.assertTrue(bot.intents.voice_states)
        self.assertTrue(bot.intents.members)
        self.assertTrue(bot.intents.message_content)

    def test_create_bot_only_syncs_recording_gateway_commands(self) -> None:
        bot = create_bot(Settings())

        command_names = {command.name for command in bot.pending_application_commands}

        self.assertEqual(command_names, {"join", "stop"})
        self.assertEqual(set(bot.cogs), {"RecordingCog"})


if __name__ == "__main__":
    unittest.main()
