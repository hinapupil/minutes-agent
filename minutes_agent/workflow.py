from __future__ import annotations

from datetime import UTC, datetime, timedelta

from agent.tools.actions import ActionExtractor
from agent.tools.minutes import GeminiMinutesGenerator
from agent.tools.transcribe import SpeechTranscriber
from minutes_agent.config import Settings
from minutes_agent.discord import DiscordNotifier
from minutes_agent.firestore import FirestoreRepository
from minutes_agent.models import (
    ActionItem,
    ActionStatus,
    GenerateMinutesRequest,
    MeetingRecord,
    MeetingStatus,
    MinutesResult,
    TranscriptSegment,
    utc_now,
)


class MinutesWorkflow:
    def __init__(
        self,
        settings: Settings,
        *,
        repository: FirestoreRepository | None = None,
        transcriber: SpeechTranscriber | None = None,
        minutes_generator: GeminiMinutesGenerator | None = None,
        action_extractor: ActionExtractor | None = None,
        notifier: DiscordNotifier | None = None,
    ) -> None:
        self._settings = settings
        self._repository = repository or FirestoreRepository(settings)
        self._transcriber = transcriber
        self._minutes_generator = minutes_generator
        self._action_extractor = action_extractor
        self._notifier = notifier or DiscordNotifier(settings)

    def generate_minutes(self, request: GenerateMinutesRequest) -> MinutesResult:
        meeting = self._repository.get_meeting(request.meeting_id)
        if meeting is None:
            meeting = MeetingRecord(
                meeting_id=request.meeting_id,
                guild_id=request.guild_id,
                channel_id=request.channel_id,
                participants=request.participants,
                audio_files=request.audio_files,
                status=MeetingStatus.TRANSCRIBING,
            )
            self._repository.save_meeting(meeting)

        try:
            self._repository.update_meeting(request.meeting_id, status=MeetingStatus.TRANSCRIBING)
            transcript_segments = self._transcribe_audio_files(meeting)
            transcript = self._render_full_transcript(meeting, transcript_segments)
            self._repository.update_meeting(
                request.meeting_id,
                status=MeetingStatus.GENERATING,
                transcript=transcript,
            )

            context = self._build_context(meeting)
            minutes_md = self._get_minutes_generator().generate(transcript, context)
            action_items = self._get_action_extractor().extract(
                request.meeting_id,
                minutes_md,
                transcript,
            )
            completed_meeting = meeting.model_copy(
                update={
                    "status": MeetingStatus.COMPLETED,
                    "transcript_segments": transcript_segments,
                    "transcript": transcript,
                    "minutes_md": minutes_md,
                    "updated_at": utc_now(),
                    "error": None,
                }
            )
            self._repository.save_meeting(completed_meeting)
            self._repository.save_action_items(action_items)
            posted = self._notifier.post_minutes(completed_meeting, action_items)
            return MinutesResult(
                meeting_id=request.meeting_id,
                minutes_md=minutes_md,
                action_items=action_items,
                posted=posted,
            )
        except Exception as exc:
            self._repository.update_meeting(
                request.meeting_id,
                status=MeetingStatus.ERROR,
                error=str(exc),
            )
            raise

    def answer_question(self, question: str, *, limit: int = 5) -> str:
        matches = self._repository.search_minutes(question, limit=limit)
        if not matches:
            return "関連する過去議事録は見つかりませんでした"
        context = "\n\n".join(
            f"## {meeting.created_at.date().isoformat()} / {meeting.meeting_id}\n"
            f"{meeting.minutes_md or meeting.render_transcript()}"
            for meeting in matches
        )
        prompt = (
            "以下の過去議事録だけを根拠に、質問へ日本語で簡潔に回答してください。\n"
            "根拠がない場合は「分かりません」と答えてください。\n\n"
            f"質問:\n{question}\n\n過去議事録:\n{context}"
        )
        return self._get_minutes_generator()._client.generate(prompt)

    def check_actions(self, now: datetime | None = None) -> list[ActionItem]:
        current = now or datetime.now(UTC)
        threshold = current + timedelta(days=2)
        pending = self._repository.list_pending_actions()
        notify_targets = [
            item
            for item in pending
            if item.due_date is None or item.due_date <= threshold
        ]
        self._notifier.post_action_reminder(notify_targets)
        return notify_targets

    def complete_action(self, action_id: str) -> ActionItem | None:
        return self._repository.complete_action(action_id)

    def list_actions(self, status: ActionStatus | None = None) -> list[ActionItem]:
        statuses: list[ActionStatus] = [status] if status else ["open", "in_progress"]
        return self._repository.list_actions(statuses=statuses)

    def _transcribe_audio_files(self, meeting: MeetingRecord) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        if not meeting.audio_files:
            raise ValueError("meeting does not contain audio files")
        for audio in meeting.audio_files:
            if not audio.gcs_uri:
                raise ValueError(f"audio artifact for {audio.speaker_id} does not have gcs_uri")
            segments.extend(
                self._get_transcriber().transcribe_uri(
                    audio.gcs_uri,
                    speaker_id=audio.speaker_id,
                    speaker_name=audio.speaker_name,
                )
            )
        return sorted(
            segments,
            key=lambda segment: (
                segment.start_seconds if segment.start_seconds is not None else 0.0,
                segment.speaker_id,
            ),
        )

    def _build_context(self, meeting: MeetingRecord) -> str:
        recent = self._repository.list_recent_minutes(before=meeting.created_at, limit=5)
        if not recent:
            return ""
        return "\n\n".join(
            f"## {item.created_at.date().isoformat()} / {item.meeting_id}\n"
            f"{item.minutes_md or item.render_transcript()}"
            for item in recent
        )

    def _render_full_transcript(
        self,
        meeting: MeetingRecord,
        transcript_segments: list[TranscriptSegment],
    ) -> str:
        lines = [segment.render() for segment in transcript_segments]
        if meeting.text_messages:
            lines.append("\n# テキストチャンネル発言")
            lines.extend(message.render() for message in meeting.text_messages)
        return "\n".join(lines).strip()

    def _get_transcriber(self) -> SpeechTranscriber:
        if self._transcriber is None:
            self._transcriber = SpeechTranscriber(self._settings)
        return self._transcriber

    def _get_minutes_generator(self) -> GeminiMinutesGenerator:
        if self._minutes_generator is None:
            self._minutes_generator = GeminiMinutesGenerator(self._settings)
        return self._minutes_generator

    def _get_action_extractor(self) -> ActionExtractor:
        if self._action_extractor is None:
            self._action_extractor = ActionExtractor(self._settings)
        return self._action_extractor
