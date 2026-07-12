from __future__ import annotations

import asyncio
import contextlib
import io
import shutil
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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

PROMPT_COOLDOWN = timedelta(minutes=5)
PROMPT_TIMEOUT_SECONDS = 600


class CompatWaveSink(discord.sinks.WaveSink):
    """py-cord 2.8 の新 voice 受信パイプラインでレガシー WaveSink を動かす互換層。

    2.8.0 は受信系を刷新したが同梱 sinks が未追随（upstream #3139）:
    - router が要求する __sink_listeners__ / walk_children() が未定義
    - write() へ bytes ではなく VoiceData(source, pcm) が渡る
    - 停止時に cleanup() が呼ばれない（呼び出し側で明示する）
    本クラスは 2.8.0 の内部実装に依存するため、バージョン更新時は要再検証。
    """

    # 補助イベント（speaking start/stop 等）は購読しない
    __sink_listeners__: list[tuple[str, str]] = []

    def is_opus(self) -> bool:
        # False = デコーダに opus→PCM 変換を要求（WaveSink は PCM 前提）
        return False

    def walk_children(self, *, with_self: bool = False) -> Iterator[CompatWaveSink]:
        if with_self:
            yield self

    def write(self, data: Any, user: Any = None) -> None:
        pcm = getattr(data, "pcm", None)
        if pcm is None:
            pcm = data if isinstance(data, (bytes, bytearray)) else b""
        if not pcm:
            return
        user_id = getattr(user, "id", None)
        if user_id is None:
            packet = getattr(data, "packet", None)
            user_id = getattr(packet, "ssrc", 0)
        if user_id not in self.audio_data:
            self.audio_data[user_id] = discord.sinks.core.AudioData(io.BytesIO())
        self.audio_data[user_id].write(pcm)


@dataclass(slots=True)
class ActiveRecording:
    meeting_id: str
    guild_id: str
    channel_id: str
    voice_channel_id: str
    text_channel: discord.abc.Messageable
    participants: list[Participant]
    text_messages: list[TextMessage]


@dataclass(slots=True)
class RecordingPrompt:
    guild_id: int
    voice_channel_id: int
    message: Any
    view: RecordingPromptView
    created_at: datetime


class RecordingPromptView(discord.ui.View):
    def __init__(
        self,
        cog: RecordingCog,
        *,
        guild_id: int,
        voice_channel_id: int,
        text_channel: discord.abc.Messageable,
    ) -> None:
        super().__init__(timeout=PROMPT_TIMEOUT_SECONDS)
        self._cog = cog
        self._guild_id = guild_id
        self._voice_channel_id = voice_channel_id
        self._text_channel = text_channel
        self.message: Any | None = None
        self._resolved = False

    @discord.ui.button(label="録音する", style=discord.ButtonStyle.success)
    async def start_recording(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        del button
        guild = interaction.guild
        member = interaction.user
        voice_state = getattr(member, "voice", None)
        if guild is None:
            await interaction.response.send_message("ギルド内で実行してください", ephemeral=True)
            return
        if voice_state is None or voice_state.channel is None:
            await interaction.response.send_message(
                "voice channel に入ってから押してください",
                ephemeral=True,
            )
            return
        if guild.id in self._cog._active:
            await interaction.response.send_message("すでに録音中です", ephemeral=True)
            await self._cog._close_recording_prompt(
                guild.id,
                "録音開始確認は終了しました。すでに録音中です",
            )
            return
        if self._resolved:
            await interaction.response.send_message("このプロンプトは対応済みです", ephemeral=True)
            return

        actor_name = getattr(member, "display_name", "不明")
        # 二重押し防止: 押した瞬間にボタンを無効化し、誰が押したかを表示する
        self._resolved = True
        self._disable_items()
        await interaction.response.edit_message(
            content=f"⏺️ {actor_name} さんが録音を開始しています...",
            view=self,
        )
        try:
            content = await self._cog._start_recording(
                guild,
                text_channel=self._text_channel,
                voice_channel=voice_state.channel,
            )
        except Exception as exc:
            # 失敗してもボタンは復活させない（再試行は新しいプロンプト or /join で）
            await self._cog._close_recording_prompt(
                guild.id,
                f"⚠️ 録音開始に失敗しました（{actor_name} さん実行）。/join で再試行可",
            )
            await interaction.followup.send(f"録音開始に失敗しました: {exc}", ephemeral=True)
            return
        await self._cog._close_recording_prompt(
            guild.id,
            f"⏺️ 録音を開始しました（開始: {actor_name} さん）\n{content}",
        )

    @discord.ui.button(label="今回はしない", style=discord.ButtonStyle.secondary)
    async def decline_recording(
        self,
        button: discord.ui.Button,
        interaction: discord.Interaction,
    ) -> None:
        del button
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("ギルド内で実行してください", ephemeral=True)
            return
        if self._resolved:
            await interaction.response.send_message("このプロンプトは対応済みです", ephemeral=True)
            return
        actor_name = getattr(interaction.user, "display_name", "不明")
        self._resolved = True
        self.stop()
        self._cog._prompts.pop(guild.id, None)
        await interaction.response.edit_message(
            content=f"🚫 今回は録音しません（{actor_name} さんが選択）",
            view=None,
        )

    async def on_timeout(self) -> None:
        await self._cog._close_recording_prompt(
            self._guild_id,
            "録音開始確認は10分経過したため終了しました",
        )

    def _disable_items(self) -> None:
        for child in self.children:
            if hasattr(child, "disabled"):
                child.disabled = True


class RecordingCog(commands.Cog):
    def __init__(self, bot: discord.Bot, settings: Settings) -> None:
        self._bot = bot
        self._settings = settings
        self._active: dict[int, ActiveRecording] = {}
        self._prompts: dict[int, RecordingPrompt] = {}
        self._last_prompted_at: dict[int, datetime] = {}

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

        # 録音の開始通知は本人だけでなくチャンネル全員に見せる（録音の透明性・同意）
        await ctx.defer()
        actor_name = getattr(ctx.author, "display_name", "不明")
        content = await self._start_recording(
            ctx.guild,
            text_channel=cast(discord.abc.Messageable, ctx.channel),
            voice_channel=voice_state.channel,
        )
        await ctx.followup.send(f"⏺️ 録音を開始しました（開始: {actor_name} さん）\n{content}")

    @discord.slash_command(name="stop", description="録音を停止して議事録生成を開始します")
    async def stop(self, ctx: discord.ApplicationContext) -> None:
        if ctx.guild is None or ctx.author is None or ctx.channel is None:
            await ctx.respond("ギルド内で実行してください", ephemeral=True)
            return
        voice_client = ctx.guild.voice_client
        if voice_client is None or ctx.guild.id not in self._active:
            await ctx.respond("録音中の会議はありません", ephemeral=True)
            return
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            voice_client.stop_recording()
        actor_name = getattr(ctx.author, "display_name", "不明")
        await ctx.respond(f"⏹️ 録音を停止しました（停止: {actor_name} さん）。議事録を生成中です...")

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
        if member.guild is None:
            return
        await self._maybe_offer_recording(member, before, after)
        await self._close_prompt_if_channel_empty(member, before, after)
        await self._stop_if_recorded_channel_empty(member, before, after)

    async def _maybe_offer_recording(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        now = datetime.now(UTC)
        guild_id = member.guild.id
        if not _should_offer_recording_prompt(
            member,
            before,
            after,
            is_active=guild_id in self._active,
            last_prompted_at=self._last_prompted_at.get(guild_id),
            now=now,
        ):
            return
        text_channel = await self._get_prompt_text_channel()
        if text_channel is None or after.channel is None:
            return
        if guild_id in self._prompts:
            return

        view = RecordingPromptView(
            self,
            guild_id=guild_id,
            voice_channel_id=after.channel.id,
            text_channel=text_channel,
        )
        message = await text_channel.send(
            f"🎙️ {member.display_name} さんが {after.channel.name} に入りました。"
            "録音を開始しますか？",
            view=view,
        )
        view.message = message
        self._prompts[guild_id] = RecordingPrompt(
            guild_id=guild_id,
            voice_channel_id=after.channel.id,
            message=message,
            view=view,
            created_at=now,
        )
        self._last_prompted_at[guild_id] = now

    async def _close_prompt_if_channel_empty(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        prompt = self._prompts.get(member.guild.id)
        if prompt is None or before.channel is None:
            return
        if before.channel.id != prompt.voice_channel_id:
            return
        if after.channel is not None and after.channel.id == before.channel.id:
            return
        if _human_members(before.channel):
            return
        await self._close_recording_prompt(
            member.guild.id,
            "全員退出したため録音開始確認を終了しました",
        )

    async def _stop_if_recorded_channel_empty(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        if member.guild.id not in self._active:
            return
        recording = self._active[member.guild.id]
        if before.channel is None or str(before.channel.id) != recording.voice_channel_id:
            return
        if after.channel is not None and str(after.channel.id) == recording.voice_channel_id:
            return
        if _human_members(before.channel):
            return
        voice_client = member.guild.voice_client
        if voice_client is not None:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                voice_client.stop_recording()

    async def _start_recording(
        self,
        guild: discord.Guild,
        *,
        text_channel: discord.abc.Messageable,
        voice_channel: discord.VoiceChannel,
    ) -> str:
        if guild.id in self._active:
            raise RuntimeError("すでに録音中です")
        voice_client = guild.voice_client
        if voice_client is None:
            voice_client = await voice_channel.connect()
        # py-cord 2.7 の型では channel が Connectable（id 属性なし）のため getattr で比較
        elif getattr(voice_client.channel, "id", None) != voice_channel.id:
            await voice_client.move_to(voice_channel)

        meeting_id = uuid4().hex
        participants = _participants_from_channel(voice_channel)
        recording = ActiveRecording(
            meeting_id=meeting_id,
            guild_id=str(guild.id),
            channel_id=str(cast(Any, text_channel).id),
            voice_channel_id=str(voice_channel.id),
            text_channel=text_channel,
            participants=participants,
            text_messages=[],
        )
        sink = CompatWaveSink()
        # 2.8 の PacketDecoder は sink.client (= self.vc) 経由で ssrc→ユーザーを解決する
        # （話者別ファイル分離のキー）。legacy の client プロパティの実体は vc
        sink.vc = voice_client

        def finished_callback(*args: object) -> None:
            error = next((arg for arg in args if isinstance(arg, Exception)), None)
            # 2.8 の after コールバックは reader スレッドから同期で呼ばれるため
            # loop.create_task ではなく thread-safe な投入を使う
            asyncio.run_coroutine_threadsafe(
                self._on_recording_finished(recording, sink, error), self._bot.loop
            )

        with warnings.catch_warnings():
            # upstream の「受信は壊れている」告知 (RuntimeWarning)。本シムで対応済みのため抑制
            warnings.simplefilter("ignore", RuntimeWarning)
            voice_client.start_recording(sink, finished_callback)
        self._active[guild.id] = recording
        return f"meeting_id: `{meeting_id}`"

    async def _get_prompt_text_channel(self) -> discord.abc.Messageable | None:
        if not self._settings.discord_channel_id:
            return None
        try:
            channel_id = int(self._settings.discord_channel_id)
        except ValueError:
            return None
        channel = self._bot.get_channel(channel_id)
        if channel is None:
            channel = await self._bot.fetch_channel(channel_id)
        if not hasattr(channel, "send"):
            return None
        return cast(discord.abc.Messageable, channel)

    async def _close_recording_prompt(self, guild_id: int, content: str) -> None:
        prompt = self._prompts.pop(guild_id, None)
        if prompt is None:
            return
        prompt.view._resolved = True
        prompt.view.stop()
        # 解決済みプロンプトはボタンを撤去し「決定の記録」テキストにする
        # （無効化ボタンを残すより、済んだ選択はテキストで伝えるのが UI 原則）
        await prompt.message.edit(content=content, view=None)

    async def _on_recording_finished(
        self,
        recording: ActiveRecording,
        sink: discord.sinks.WaveSink,
        error: Exception | None,
    ) -> None:
        guild_id_int = int(recording.guild_id)
        self._active.pop(guild_id_int, None)
        try:
            if error is not None:
                await recording.text_channel.send(f"録音終了処理でエラーが発生しました: {error}")
                return
            if not getattr(sink, "finished", False):
                sink.cleanup()  # 2.8 の reader は cleanup を呼ばない（wav ヘッダ付与に必須）
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
        finally:
            # 録音が終わったら（成功・失敗問わず）voice channel から退出する。
            # これが無いと Bot が誰もいないチャンネルに残り続ける
            await self._disconnect_voice(guild_id_int)

    async def _disconnect_voice(self, guild_id: int) -> None:
        guild = self._bot.get_guild(guild_id)
        voice_client = guild.voice_client if guild else None
        if voice_client is None:
            return
        # 退出失敗は致命的でない（次の join で move_to される）
        with contextlib.suppress(Exception):
            await voice_client.disconnect(force=True)

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
        for member in _human_members(channel)
    ]


def _human_members(channel: Any) -> list[Any]:
    return [
        member
        for member in getattr(channel, "members", [])
        if not getattr(member, "bot", False)
    ]


def _should_offer_recording_prompt(
    member: Any,
    before: Any,
    after: Any,
    *,
    is_active: bool,
    last_prompted_at: datetime | None,
    now: datetime,
) -> bool:
    if getattr(member, "bot", False) or is_active:
        return False
    before_channel = getattr(before, "channel", None)
    after_channel = getattr(after, "channel", None)
    if after_channel is None:
        return False
    if before_channel is not None and before_channel.id == after_channel.id:
        return False
    if len(_human_members(after_channel)) != 1:
        return False
    return last_prompted_at is None or now - last_prompted_at >= PROMPT_COOLDOWN
