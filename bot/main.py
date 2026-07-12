from __future__ import annotations

import logging

import discord

# --- DAVE (E2EE) オプトアウト ---
# py-cord 2.8 は davey 同梱時に max_dave_protocol_version>0 を申告し通話が
# E2EE のまま維持されるが、受信側の DAVE 復号が未実装（pycord#3139）のため
# 録音が corrupted stream で壊れる。davey を uninstall すると
# voice/__init__.py が import 時に MissingVoiceDependenciesError を投げるため、
# davey は残したまま申告バージョンだけ 0 に固定する。
# 申告 0 なら DAVE 移行期の仕様で Discord が通話を非E2EE にダウングレードし、
# 平文 opus を受信できる（Craig 等の既存録音ボットと同じ動作条件）。
# upstream の受信側 DAVE 対応（pycord#3159, milestone 2.9）が入ったら削除 → issue #34
import discord.voice.state as _voice_state

from bot.commands.recording import RecordingCog
from minutes_agent.config import Settings, get_settings

_voice_state.DAVE_PROTOCOL_VERSION = 0

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
