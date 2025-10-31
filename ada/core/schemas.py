from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Contact(BaseModel):
    id: str
    email: str | None
    first_name: str | None
    last_name: str | None
    owner_id: str | None
    lifecycle: str | None
    last_modified: datetime | None
    score: float | None
    source: str | None = "hubspot"

    def to_dict(self) -> dict[str, Any]:
        return self.dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Contact:
        return cls(**data)


class Message(BaseModel):
    id: str
    client_slug: str
    contact_id: str
    channel: str = "gmail"
    role: Literal["system", "assistant", "user"] = "assistant"
    subject: str | None
    body: str | None
    ts: datetime
    status: Literal["draft", "approved", "queued", "sent", "failed"] = "draft"
    meta: dict[str, Any] = Field(default_factory=dict)


class Thread(BaseModel):
    id: str
    client_slug: str
    contact_id: str
    channel: str = "gmail"
    last_ts: datetime | None
    meta: dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    client_slug: str
    kind: Literal["opened", "replied", "bounced", "opted_out", "rate_limited", "sent"]
    contact_id: str | None
    message_id: str | None
    ts: datetime
    meta: dict[str, Any] = Field(default_factory=dict)


class Metric(BaseModel):
    client_slug: str
    window: str
    contacts: int
    contacted: int
    replies: int
    meetings: int
    open_rate: float
    reply_rate: float
    conversion_rate: float
    ts: datetime


class OutreachPlan(BaseModel):
    client_slug: str
    generated_at: datetime
    targets: list[str] = Field(default_factory=list)
    daily_cap: int = 25
    variant: str | None
    reasons_by_contact: dict[str, str] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.dict()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OutreachPlan:
        return cls(**data)
