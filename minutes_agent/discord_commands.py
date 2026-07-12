from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any

from minutes_agent.config import Settings, get_settings

DISCORD_API_BASE = "https://discord.com/api/v10"
OPTION_STRING = 3
OPTION_ATTACHMENT = 11


def interaction_command_payloads() -> list[dict[str, Any]]:
    return [
        {
            "name": "minutes",
            "description": "音声ファイルまたは zip から議事録を生成します",
            "options": [
                {
                    "name": "file",
                    "description": "音声ファイルまたは zip",
                    "type": OPTION_ATTACHMENT,
                    "required": True,
                }
            ],
        },
        {
            "name": "ask",
            "description": "過去の議事録に関する質問をします",
            "options": [
                {
                    "name": "question",
                    "description": "質問",
                    "type": OPTION_STRING,
                    "required": True,
                }
            ],
        },
        {
            "name": "actions",
            "description": "アクションアイテムを表示します",
            "options": [
                {
                    "name": "status",
                    "description": "open / in_progress / completed",
                    "type": OPTION_STRING,
                    "required": False,
                    "choices": [
                        {"name": "open", "value": "open"},
                        {"name": "in_progress", "value": "in_progress"},
                        {"name": "completed", "value": "completed"},
                    ],
                }
            ],
        },
        {
            "name": "action-done",
            "description": "アクションアイテムを完了にします",
            "options": [
                {
                    "name": "id",
                    "description": "Action item ID",
                    "type": OPTION_STRING,
                    "required": True,
                }
            ],
        },
    ]


def register_interaction_commands(
    settings: Settings | None = None,
    *,
    guild_id: str | None = None,
) -> list[dict[str, Any]]:
    actual_settings = settings or get_settings()
    actual_settings.require("discord_bot_token", "discord_application_id")
    application_id = str(actual_settings.discord_application_id)
    url = f"{DISCORD_API_BASE}/applications/{application_id}/commands"
    if guild_id:
        url = f"{DISCORD_API_BASE}/applications/{application_id}/guilds/{guild_id}/commands"
    payload = json.dumps(interaction_command_payloads()).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bot {actual_settings.discord_bot_token}",
            "Content-Type": "application/json",
            "User-Agent": "MinutesAgent (https://github.com/hinapupil/minutes-agent, 0.1)",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
    decoded = json.loads(body)
    if not isinstance(decoded, list):
        raise RuntimeError(f"unexpected Discord response: {decoded!r}")
    return decoded


def main() -> None:
    parser = argparse.ArgumentParser(description="Register Discord interaction commands")
    parser.add_argument(
        "--guild-id",
        default=None,
        help="Register guild commands for fast propagation. Omit for global commands.",
    )
    args = parser.parse_args()
    commands = register_interaction_commands(guild_id=args.guild_id)
    names = ", ".join(str(command.get("name")) for command in commands)
    print(f"registered commands: {names}")


if __name__ == "__main__":
    main()
