from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import BackgroundTasks, HTTPException, Request

from minutes_agent.config import Settings
from minutes_agent.discord import DiscordNotifier, verify_discord_signature
from minutes_agent.firestore import FirestoreRepository
from minutes_agent.models import AudioArtifact, GenerateMinutesRequest, MeetingRecord, Participant
from minutes_agent.storage import GcsStorage
from minutes_agent.tasks import CloudTasksPublisher
from minutes_agent.workflow import MinutesWorkflow

INTERACTION_PING = 1
INTERACTION_APPLICATION_COMMAND = 2

RESPONSE_PONG = 1
RESPONSE_CHANNEL_MESSAGE = 4
RESPONSE_DEFERRED_CHANNEL_MESSAGE = 5

DOWNLOAD_CHUNK_BYTES = 1024 * 1024


async def handle_interaction(
    request: Request,
    background_tasks: BackgroundTasks,
    settings: Settings,
) -> dict[str, Any]:
    body = await request.body()
    signature = request.headers.get("X-Signature-Ed25519")
    timestamp = request.headers.get("X-Signature-Timestamp")
    if not settings.discord_public_key:
        raise HTTPException(status_code=500, detail="DISCORD_PUBLIC_KEY is not configured")
    if not signature or not timestamp:
        raise HTTPException(status_code=401, detail="Missing Discord signature headers")
    if not verify_discord_signature(settings.discord_public_key, timestamp, signature, body):
        raise HTTPException(status_code=401, detail="Invalid Discord signature")

    payload = json.loads(body.decode("utf-8"))
    interaction_type = payload.get("type")
    if interaction_type == INTERACTION_PING:
        return {"type": RESPONSE_PONG}
    if interaction_type != INTERACTION_APPLICATION_COMMAND:
        return _message("Unsupported interaction type", ephemeral=True)

    command_name = payload.get("data", {}).get("name")
    application_id = str(payload.get("application_id") or settings.discord_application_id or "")
    token = str(payload.get("token") or "")
    guild_id = str(payload.get("guild_id") or "")
    channel_id = str(payload.get("channel_id") or settings.discord_channel_id or "")

    if command_name == "ask":
        question = str(_option_value(payload, "question") or "").strip()
        if not question:
            return _message("question が空です", ephemeral=True)
        background_tasks.add_task(
            _answer_question_followup,
            settings,
            application_id,
            token,
            guild_id,
            channel_id,
            question,
        )
        return {"type": RESPONSE_DEFERRED_CHANNEL_MESSAGE}

    if command_name == "actions":
        status = _option_value(payload, "status")
        workflow = MinutesWorkflow(settings)
        actions = workflow.list_actions(status=status)
        return _message(_format_actions(actions), ephemeral=True)

    if command_name == "action-done":
        action_id = str(_option_value(payload, "id") or "").strip()
        if not action_id:
            return _message("id が空です", ephemeral=True)
        workflow = MinutesWorkflow(settings)
        item = workflow.complete_action(action_id)
        if item is None:
            return _message(f"`{action_id}` は見つかりませんでした", ephemeral=True)
        return _message(f"`{action_id}` を完了にしました", ephemeral=True)

    if command_name == "minutes":
        attachment = _attachment_option(payload, "file")
        if attachment is None:
            return _message("file attachment が必要です", ephemeral=True)
        background_tasks.add_task(
            _enqueue_attachment_minutes,
            settings,
            application_id,
            token,
            guild_id,
            channel_id,
            attachment,
        )
        return {"type": RESPONSE_DEFERRED_CHANNEL_MESSAGE}

    return _message(f"Unsupported command: {command_name}", ephemeral=True)


def _answer_question_followup(
    settings: Settings,
    application_id: str,
    token: str,
    guild_id: str,
    channel_id: str,
    question: str,
) -> None:
    notifier = DiscordNotifier(settings)
    try:
        answer = MinutesWorkflow(settings).answer_question(
            question,
            user_id=_discord_user_id(guild_id),
            session_id=_ask_session_id(guild_id, channel_id),
        )
    except Exception as exc:
        answer = f"質問処理に失敗しました: {exc}"
    notifier.send_interaction_followup(application_id, token, answer)


def _enqueue_attachment_minutes(
    settings: Settings,
    application_id: str,
    token: str,
    guild_id: str,
    channel_id: str,
    attachment: dict[str, Any],
) -> None:
    notifier = DiscordNotifier(settings)
    try:
        meeting_id = uuid4().hex
        audio_files = _download_upload_attachment(settings, meeting_id, attachment)
        participants = [Participant(user_id="manual-upload", display_name="manual-upload")]
        meeting = MeetingRecord(
            meeting_id=meeting_id,
            guild_id=guild_id or "unknown",
            channel_id=channel_id or "unknown",
            participants=participants,
            audio_files=audio_files,
        )
        FirestoreRepository(settings).save_meeting(meeting)
        publisher = CloudTasksPublisher(settings)
        task_name = publisher.enqueue_generate_minutes(
            GenerateMinutesRequest(
                meeting_id=meeting_id,
                guild_id=meeting.guild_id,
                channel_id=meeting.channel_id,
                participants=participants,
                audio_files=audio_files,
            )
        )
        content = f"議事録生成ジョブを登録しました\nmeeting_id: `{meeting_id}`\ntask: `{task_name}`"
    except Exception as exc:
        content = f"添付ファイルの処理に失敗しました: {exc}"
    notifier.send_interaction_followup(application_id, token, content, ephemeral=True)


def _download_upload_attachment(
    settings: Settings,
    meeting_id: str,
    attachment: dict[str, Any],
) -> list[AudioArtifact]:
    url = str(attachment.get("url") or "")
    filename = str(attachment.get("filename") or "attachment")
    if not url:
        raise ValueError("attachment url is empty")
    storage = GcsStorage(settings)
    with tempfile.TemporaryDirectory() as temp_dir:
        download_path = Path(temp_dir) / _safe_attachment_filename(filename)
        _download_attachment(
            url,
            download_path,
            max_bytes=settings.interaction_attachment_max_bytes,
        )
        paths = _expand_audio_files(download_path, Path(temp_dir) / "expanded")
        audio_files: list[AudioArtifact] = []
        for index, path in enumerate(paths, start=1):
            speaker_id = f"manual-{index}"
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


def _safe_attachment_filename(filename: str) -> str:
    return Path(filename.replace("\\", "/")).name or "attachment"


def _download_attachment(url: str, download_path: Path, *, max_bytes: int) -> None:
    if max_bytes <= 0:
        raise ValueError("attachment max bytes must be positive")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "MinutesAgent (https://github.com/hinapupil/minutes-agent, 0.1)"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None:
                try:
                    declared_size = int(content_length)
                except ValueError:
                    declared_size = None
                if declared_size is not None and declared_size > max_bytes:
                    raise ValueError("attachment too large")
            _write_limited_response(response, download_path, max_bytes=max_bytes)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"attachment download returned HTTP {exc.code}: {exc.read()!r}") from exc


def _write_limited_response(response: Any, download_path: Path, *, max_bytes: int) -> None:
    download_path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with download_path.open("wb") as file:
        while True:
            chunk = response.read(min(DOWNLOAD_CHUNK_BYTES, max_bytes - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("attachment too large")
            file.write(chunk)


def _expand_audio_files(path: Path, output_dir: Path) -> list[Path]:
    audio_suffixes = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".opus", ".webm"}
    if path.suffix.lower() != ".zip":
        if path.suffix.lower() not in audio_suffixes:
            raise ValueError(f"unsupported attachment type: {path.suffix}")
        return [path]
    output_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        _extract_zip_safely(archive, output_dir)
    audio_files = [
        child
        for child in output_dir.rglob("*")
        if child.is_file() and child.suffix.lower() in audio_suffixes
    ]
    if not audio_files:
        raise ValueError("zip did not contain supported audio files")
    return audio_files


def _extract_zip_safely(archive: zipfile.ZipFile, output_dir: Path) -> None:
    root = output_dir.resolve()
    for member in archive.infolist():
        target = (output_dir / member.filename).resolve()
        if not target.is_relative_to(root):
            raise ValueError("zip contains unsafe path")
        if member.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, target.open("wb") as destination:
            shutil.copyfileobj(source, destination)


def _option_value(payload: dict[str, Any], name: str) -> Any:
    options = payload.get("data", {}).get("options", []) or []
    for option in options:
        if option.get("name") == name:
            return option.get("value")
    return None


def _attachment_option(payload: dict[str, Any], name: str) -> dict[str, Any] | None:
    attachment_id = _option_value(payload, name)
    if attachment_id is None:
        return None
    attachments = payload.get("data", {}).get("resolved", {}).get("attachments", {}) or {}
    attachment = attachments.get(str(attachment_id))
    return attachment if isinstance(attachment, dict) else None


def _message(content: str, *, ephemeral: bool) -> dict[str, Any]:
    payload: dict[str, Any] = {"content": content}
    if ephemeral:
        payload["flags"] = 64
    return {"type": RESPONSE_CHANNEL_MESSAGE, "data": payload}


def _format_actions(actions: list[Any]) -> str:
    if not actions:
        return "未完了のアクションアイテムはありません"
    lines = ["未完了アクションアイテム"]
    for item in actions:
        due = item.due_date.date().isoformat() if item.due_date else "期限未設定"
        assignee = item.assignee or "担当者未設定"
        lines.append(f"- `{item.action_id}` {item.title} / {assignee} / {due}")
    return "\n".join(lines)


def _discord_user_id(guild_id: str) -> str:
    return f"discord-guild:{guild_id or 'dm'}"


def _ask_session_id(guild_id: str, channel_id: str) -> str:
    return f"ask:{guild_id or 'dm'}:{channel_id or 'unknown'}"
