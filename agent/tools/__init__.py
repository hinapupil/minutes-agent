from __future__ import annotations

from agent.tools.actions import ActionExtractor
from agent.tools.discord_notify import send_discord_message
from agent.tools.minutes import GeminiMinutesGenerator
from agent.tools.search import get_pending_actions, search_minutes
from agent.tools.transcribe import SpeechTranscriber
from minutes_agent.config import get_settings


def transcribe_audio(gcs_uri: str, speaker_name: str | None = None) -> str:
    settings = get_settings()
    segments = SpeechTranscriber(settings).transcribe_uri(
        gcs_uri,
        speaker_id=speaker_name or "speaker",
        speaker_name=speaker_name,
    )
    return "\n".join(segment.render() for segment in segments)


def generate_minutes(transcript: str, context: str = "") -> str:
    settings = get_settings()
    return GeminiMinutesGenerator(settings).generate(transcript, context)


def extract_action_items(
    meeting_id: str,
    minutes_md: str,
    transcript: str = "",
) -> list[dict[str, object]]:
    settings = get_settings()
    items = ActionExtractor(settings).extract(meeting_id, minutes_md, transcript)
    return [item.model_dump(mode="json") for item in items]


__all__ = [
    "ActionExtractor",
    "GeminiMinutesGenerator",
    "SpeechTranscriber",
    "extract_action_items",
    "generate_minutes",
    "get_pending_actions",
    "search_minutes",
    "send_discord_message",
    "transcribe_audio",
]
