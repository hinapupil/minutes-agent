from __future__ import annotations

from minutes_agent.config import get_settings
from minutes_agent.discord import DiscordNotifier


def send_discord_message(content: str) -> bool:
    settings = get_settings()
    if not settings.discord_webhook_url:
        return False
    notifier = DiscordNotifier(settings)
    notifier._post_json(settings.discord_webhook_url, {"content": content})
    return True

