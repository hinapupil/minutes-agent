from __future__ import annotations

import logging

import discord

from bot.commands.actions import ActionsCog
from bot.commands.ask import AskCog
from bot.commands.recording import RecordingCog
from minutes_agent.config import Settings, get_settings

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


def create_bot(settings: Settings | None = None) -> discord.Bot:
    actual_settings = settings or get_settings()
    intents = discord.Intents.default()
    intents.guilds = True
    intents.voice_states = True
    intents.members = True
    intents.message_content = True

    bot = discord.Bot(intents=intents)
    bot.add_cog(RecordingCog(bot, actual_settings))
    bot.add_cog(AskCog(actual_settings))
    bot.add_cog(ActionsCog(actual_settings))

    @bot.event
    async def on_ready() -> None:
        LOGGER.info("Logged in as %s", bot.user)

    return bot


def main() -> None:
    settings = get_settings()
    settings.require("discord_bot_token")
    bot = create_bot(settings)
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    main()
