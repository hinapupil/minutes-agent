from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from minutes_agent.models import ActionStatus


class AskCommandRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    question: str
    limit: int = Field(default=5, ge=1, le=10)


class CompleteActionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action_id: str


class ActionsCommandRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: ActionStatus | None = None
    limit: int = Field(default=100, ge=1, le=200)
