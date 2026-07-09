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


if __name__ == "__main__":
    unittest.main()
