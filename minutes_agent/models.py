from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class MeetingStatus(StrEnum):
    RECORDING = "recording"
    TRANSCRIBING = "transcribing"
    GENERATING = "generating"
    COMPLETED = "completed"
    ERROR = "error"


ActionStatus = Literal["open", "in_progress", "completed"]


class Participant(BaseModel):
    model_config = ConfigDict(extra="ignore")

    user_id: str
    display_name: str | None = None


class AudioArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speaker_id: str
    speaker_name: str | None = None
    local_path: str | None = None
    gcs_uri: str | None = None
    content_type: str = "audio/wav"


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(extra="ignore")

    speaker_id: str
    speaker_name: str | None = None
    text: str
    start_seconds: float | None = None
    end_seconds: float | None = None

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("transcript segment text must not be empty")
        return stripped

    def render(self) -> str:
        speaker = self.speaker_name or self.speaker_id
        if self.start_seconds is None:
            return f"{speaker}: {self.text}"
        return f"[{self.start_seconds:0.1f}s] {speaker}: {self.text}"


class TextMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: str
    author_id: str
    author_name: str | None = None
    content: str
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("text message content must not be empty")
        return stripped

    def render(self) -> str:
        author = self.author_name or self.author_id
        timestamp = self.created_at.isoformat()
        return f"[text:{timestamp}] {author}: {self.content}"


class MeetingRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meeting_id: str = Field(default_factory=lambda: uuid4().hex)
    guild_id: str
    channel_id: str
    participants: list[Participant] = Field(default_factory=list)
    audio_files: list[AudioArtifact] = Field(default_factory=list)
    text_messages: list[TextMessage] = Field(default_factory=list)
    transcript_segments: list[TranscriptSegment] = Field(default_factory=list)
    transcript: str | None = None
    minutes_md: str | None = None
    status: MeetingStatus = MeetingStatus.RECORDING
    error: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    def render_transcript(self) -> str:
        if self.transcript:
            return self.transcript.strip()
        return "\n".join(segment.render() for segment in self.transcript_segments).strip()


class ActionItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    meeting_id: str
    title: str
    description: str = ""
    assignee: str | None = None
    assignee_id: str | None = None
    due_date: datetime | None = None
    status: ActionStatus = "open"
    source_quote: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("action title must not be empty")
        return stripped


class GenerateMinutesRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meeting_id: str
    guild_id: str
    channel_id: str
    participants: list[Participant] = Field(default_factory=list)
    audio_files: list[AudioArtifact] = Field(default_factory=list)


class MinutesResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meeting_id: str
    minutes_md: str
    action_items: list[ActionItem]
    posted: bool
