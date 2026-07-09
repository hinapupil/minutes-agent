from __future__ import annotations

from datetime import datetime
from typing import Any, cast

from minutes_agent.config import Settings
from minutes_agent.models import ActionItem, ActionStatus, MeetingRecord, MeetingStatus, utc_now


def _dump_model(model: Any) -> dict[str, Any]:
    return cast(dict[str, Any], model.model_dump(mode="python"))


class FirestoreRepository:
    def __init__(self, settings: Settings) -> None:
        settings.require("google_cloud_project")
        from google.cloud import firestore

        self._client = firestore.Client(project=settings.google_cloud_project)

    def save_meeting(self, meeting: MeetingRecord) -> None:
        data = _dump_model(meeting.model_copy(update={"updated_at": utc_now()}))
        self._client.collection("meetings").document(meeting.meeting_id).set(data, merge=True)

    def get_meeting(self, meeting_id: str) -> MeetingRecord | None:
        snapshot = self._client.collection("meetings").document(meeting_id).get()
        if not snapshot.exists:
            return None
        return MeetingRecord.model_validate(snapshot.to_dict())

    def update_meeting(
        self,
        meeting_id: str,
        *,
        status: MeetingStatus | None = None,
        transcript: str | None = None,
        minutes_md: str | None = None,
        error: str | None = None,
    ) -> None:
        patch: dict[str, Any] = {"updated_at": utc_now()}
        if status is not None:
            patch["status"] = status.value
        if transcript is not None:
            patch["transcript"] = transcript
        if minutes_md is not None:
            patch["minutes_md"] = minutes_md
        if error is not None:
            patch["error"] = error
        self._client.collection("meetings").document(meeting_id).set(patch, merge=True)

    def save_action_items(self, action_items: list[ActionItem]) -> None:
        if not action_items:
            return
        batch = self._client.batch()
        collection = self._client.collection("action_items")
        for item in action_items:
            batch.set(collection.document(item.action_id), _dump_model(item), merge=True)
        batch.commit()

    def list_actions(
        self,
        *,
        statuses: list[ActionStatus] | None = None,
        limit: int = 100,
    ) -> list[ActionItem]:
        selected_statuses = statuses or ["open", "in_progress"]
        query = (
            self._client.collection("action_items")
            .where("status", "in", selected_statuses)
            .limit(limit)
        )
        return [ActionItem.model_validate(snapshot.to_dict()) for snapshot in query.stream()]

    def list_pending_actions(self, limit: int = 100) -> list[ActionItem]:
        return self.list_actions(statuses=["open", "in_progress"], limit=limit)

    def complete_action(self, action_id: str) -> ActionItem | None:
        reference = self._client.collection("action_items").document(action_id)
        snapshot = reference.get()
        if not snapshot.exists:
            return None
        item = ActionItem.model_validate(snapshot.to_dict()).model_copy(
            update={"status": "completed", "completed_at": utc_now()}
        )
        reference.set(_dump_model(item), merge=True)
        return item

    def search_minutes(self, query_text: str, limit: int = 5) -> list[MeetingRecord]:
        lowered = query_text.lower().strip()
        query = (
            self._client.collection("meetings")
            .order_by("created_at", direction="DESCENDING")
            .limit(50)
        )
        matches: list[MeetingRecord] = []
        for snapshot in query.stream():
            meeting = MeetingRecord.model_validate(snapshot.to_dict())
            haystack = f"{meeting.minutes_md or ''}\n{meeting.render_transcript()}".lower()
            if not lowered or lowered in haystack:
                matches.append(meeting)
            if len(matches) >= limit:
                break
        return matches

    def list_recent_minutes(
        self,
        before: datetime | None = None,
        limit: int = 5,
    ) -> list[MeetingRecord]:
        query = (
            self._client.collection("meetings")
            .order_by("created_at", direction="DESCENDING")
            .limit(limit)
        )
        meetings: list[MeetingRecord] = []
        for snapshot in query.stream():
            meeting = MeetingRecord.model_validate(snapshot.to_dict())
            if before is None or meeting.created_at < before:
                meetings.append(meeting)
        return meetings
