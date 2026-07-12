from __future__ import annotations

import logging

import discord

# DAVE(E2EE) メモ: 「申告0で非E2EEにダウングレード」は Discord 側が 4017 で拒否する
# ため不可（移行期仕様は終了済み・2026-07-12 E2E実測）。現在は DAVE 実装が録音の
# 必須条件のため、受信側 DAVE 復号を実装した upstream ブランチ pycord#3159 を
# SHA 固定で先取りしている（requirements.txt 参照）。2.9 正式リリース後に
# 通常のバージョン指定へ戻す → issue #34
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
