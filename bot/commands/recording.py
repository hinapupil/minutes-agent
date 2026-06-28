from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

import discord
from discord.ext import commands

from minutes_agent.config import Settings
from minutes_agent.firestore import FirestoreRepository
from minutes_agent.models import (
    AudioArtifact,
    GenerateMinutesRequest,
    MeetingRecord,
    Participant,
    TextMessage,
)
from minutes_agent.storage import GcsStorage
from minutes_agent.tasks import CloudTasksPublisher


@dataclass(slots=True)
class ActiveRecording:
    meeting_id: str
    guild_id: str
    channel_id: str
    voice_channel_id: str
    text_channel: discord.abc.Messageable
    participants: list[Participant]
    text_messages: list[TextMessage]


class RecordingCog(commands.Cog):
    def __init__(self, bot: discord.Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings
        self._active: dict[int, ActiveRecording] = {}

    @discord.slash_command(name="join", description="Voice channel に参加して録音を開始します")
    async def join(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild is None or ctx.author is None or ctx.channel is None:
            await ctx.respond("ギルド内で実行してください", ephemeral=True)
            return
        voice_state = getattr(ctx.author, "voice", None)
        if voice_state is None or voice_state.channel is None:
            await ctx.respond("先に voice channel に参加してください", ephemeral=True)
            return
        if ctx.guild.id in self._active:
            await ctx.respond("すでに録音中です", ephemeral=True)
            return

        await ctx.defer(ephemeral=True)
        voice_client = ctx.guild.voice_client
        if voice_client is None:
            voice_client = await voice_state.channel.connect()
        elif voice_client.channel.id != voice_state.channel.id:
            await voice_client.move_to(voice_state.channel)

        meeting_id = uuid4().hex
        participants = _participants_from_channel(voice_state.channel)
        recording = ActiveRecording(
            meeting_id=meeting_id,
            guild_id=str(ctx.guild.id),
            channel_id=str(ctx.channel.id),
            voice_channel_id=str(voice_state.channel.id),
            text_channel=cast(discord.abc.Messageable, ctx.channel),
            participants=participants,
            text_messages=[],
        )
        sink = discord.sinks.WaveSink()

        def finished_callback(*args: object) -> None:
            error = next((arg for arg in args if isinstance(arg, Exception)), None)
            self._bot.loop.create_task(self._on_recording_finished(recording, sink, error))

        voice_client.start_recording(sink, finished_callback)
        self._active[ctx.guild.id] = recording
        await ctx.followup.send(f"録音を開始しました\nmeeting_id: `{meeting_id}`", ephemeral=True)

    @discord.slash_command(name="stop", description="録音を停止して議事録生成を開始します")
    async def stop(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild is None or ctx.author is None or ctx.channel is None:
            await ctx.respond("ギルド内で実行してください", ephemeral=True)
            return
        voice_client = ctx.guild.voice_client
        if voice_client is None or ctx.guild.id not in self._active:
            await ctx.respond("録音中の会議はありません", ephemeral=True)
            return
        voice_client.stop_recording()
        await ctx.respond("録音を停止しました。議事録生成ジョブを登録します", ephemeral=True)

    @discord.slash_command(
        name="minutes",
        description="音声ファイルまたは zip から議事録を生成します",
    )
    async def minutes(self, ctx: discord.ApplicationContext, file: discord.Attachment) -> None:
        if ctx.guild is None:
            await ctx.respond("ギルド内で実行してください", ephemeral=True)
            return
        await ctx.defer(ephemeral=True)
        meeting_id = uuid4().hex
        target_dir = self._settings.local_recordings_dir / meeting_id / "manual"
        target_dir.mkdir(parents=True, exist_ok=True)
        downloaded = target_dir / file.filename
        await file.save(downloaded)
        try:
            expanded_files = _expand_audio_files(downloaded, target_dir / "zip")
            audio_files = self._upload_paths(meeting_id, expanded_files)
            participants = [Participant(user_id=str(ctx.author.id), display_name=str(ctx.author))]
            channel_id = str(cast(Any, ctx.channel).id)
            request = GenerateMinutesRequest(
                meeting_id=meeting_id,
                guild_id=str(ctx.guild.id),
                channel_id=channel_id,
                participants=participants,
                audio_files=audio_files,
            )
            FirestoreRepository(self._settings).save_meeting(
                MeetingRecord(
                    meeting_id=meeting_id,
                    guild_id=request.guild_id,
                    channel_id=request.channel_id,
                    participants=participants,
                    audio_files=audio_files,
                    text_messages=[],
                )
            )
            task_name = CloudTasksPublisher(self._settings).enqueue_generate_minutes(request)
            await ctx.followup.send(
                f"議事録生成ジョブを登録しました\nmeeting_id: `{meeting_id}`\ntask: `{task_name}`",
                ephemeral=True,
            )
        except Exception as exc:
            await ctx.followup.send(f"添付ファイル処理に失敗しました: {exc}", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.guild is None or message.author.bot:
            return
        recording = self._active.get(message.guild.id)
        if recording is None or str(message.channel.id) != recording.channel_id:
            return
        if not message.content.strip():
            return
        recording.text_messages.append(
            TextMessage(
                message_id=str(message.id),
                author_id=str(message.author.id),
                author_name=message.author.display_name,
                content=message.content,
                created_at=message.created_at,
            )
        )

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.guild is None or member.guild.id not in self._active:
            return
        recording = self._active[member.guild.id]
        if before.channel is None or str(before.channel.id) != recording.voice_channel_id:
            return
        if after.channel is not None and str(after.channel.id) == recording.voice_channel_id:
            return
        humans = [voice_member for voice_member in before.channel.members if not voice_member.bot]
        if humans:
            return
        voice_client = member.guild.voice_client
        if voice_client is not None:
            voice_client.stop_recording()

    async def _on_recording_finished(
        self,
        recording: ActiveRecording,
        sink: discord.sinks.WaveSink,
        error: Exception | None,
    ) -> None:
        guild_id_int = int(recording.guild_id)
        self._active.pop(guild_id_int, None)
        if error is not None:
            await recording.text_channel.send(f"録音終了処理でエラーが発生しました: {error}")
            return
        try:
            local_paths = self._save_sink_audio(recording.meeting_id, sink)
            audio_files = self._upload_paths(recording.meeting_id, local_paths)
            request = GenerateMinutesRequest(
                meeting_id=recording.meeting_id,
                guild_id=recording.guild_id,
                channel_id=recording.channel_id,
                participants=recording.participants,
                audio_files=audio_files,
            )
            FirestoreRepository(self._settings).save_meeting(
                MeetingRecord(
                    meeting_id=recording.meeting_id,
                    guild_id=recording.guild_id,
                    channel_id=recording.channel_id,
                    participants=recording.participants,
                    audio_files=audio_files,
                    text_messages=recording.text_messages,
                )
            )
            task_name = CloudTasksPublisher(self._settings).enqueue_generate_minutes(request)
            await recording.text_channel.send(
                "議事録生成ジョブを登録しました\n"
                f"meeting_id: `{recording.meeting_id}`\n"
                f"task: `{task_name}`"
            )
        except Exception as exc:
            await recording.text_channel.send(
                f"録音は終了しましたが、議事録生成ジョブ登録に失敗しました: {exc}"
            )

    def _save_sink_audio(self, meeting_id: str, sink: discord.sinks.WaveSink) -> list[Path]:
        output_dir = self._settings.local_recordings_dir / meeting_id
        output_dir.mkdir(parents=True, exist_ok=True)
        paths: list[Path] = []
        audio_data = getattr(sink, "audio_data", {})
        for user_id, audio in audio_data.items():
            source = getattr(audio, "file", None)
            if source is None:
                continue
            source.seek(0)
            path = output_dir / f"{user_id}.wav"
            with path.open("wb") as target:
                shutil.copyfileobj(source, target)
            paths.append(path)
        if not paths:
            raise RuntimeError("recording sink did not contain audio")
        return paths

    def _upload_paths(self, meeting_id: str, paths: list[Path]) -> list[AudioArtifact]:
        storage = GcsStorage(self._settings)
        audio_files: list[AudioArtifact] = []
        for path in paths:
            speaker_id = path.stem
            gcs_uri = storage.upload_audio_file(path, meeting_id, speaker_id)
            audio_files.append(
                AudioArtifact(
                    speaker_id=speaker_id,
                    speaker_name=path.stem,
                    local_path=str(path),
                    gcs_uri=gcs_uri,
                )
            )
        return audio_files


def _participants_from_channel(channel: discord.VoiceChannel) -> list[Participant]:
    return [
        Participant(user_id=str(member.id), display_name=member.display_name)
        for member in channel.members
        if not member.bot
    ]


def _expand_audio_files(path: Path, output_dir: Path) -> list[Path]:
    audio_suffixes = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".webm"}
    if path.suffix.lower() != ".zip":
        if path.suffix.lower() not in audio_suffixes:
            raise ValueError(f"unsupported attachment type: {path.suffix}")
        return [path]
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        archive.extractall(output_dir)
    files = [
        child
        for child in output_dir.rglob("*")
        if child.is_file() and child.suffix.lower() in audio_suffixes
    ]
    if not files:
        raise ValueError("zip did not contain supported audio files")
    return files
