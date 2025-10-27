from __future__ import annotations
from typing import Literal, Any, Dict, List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class Contact(BaseModel):
    id: str
    email: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    owner_id: Optional[str]
    lifecycle: Optional[str]
    last_modified: Optional[datetime]
    score: Optional[float]
    source: Optional[str] = "hubspot"

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Contact":
        return cls(**data)


class Message(BaseModel):
    id: str
    client_slug: str
    contact_id: str
    channel: str = "gmail"
    role: Literal["system", "assistant", "user"] = "assistant"
    subject: Optional[str]
    body: Optional[str]
    ts: datetime
    status: Literal["draft", "approved", "queued", "sent", "failed"] = "draft"
    meta: Dict[str, Any] = Field(default_factory=dict)


class Thread(BaseModel):
    id: str
    client_slug: str
    contact_id: str
    channel: str = "gmail"
    last_ts: Optional[datetime]
    meta: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    client_slug: str
    kind: Literal["opened", "replied", "bounced", "opted_out", "rate_limited", "sent"]
    contact_id: Optional[str]
    message_id: Optional[str]
    ts: datetime
    meta: Dict[str, Any] = Field(default_factory=dict)


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
    targets: List[str] = Field(default_factory=list)
    daily_cap: int = 25
    variant: Optional[str]

    def to_dict(self) -> Dict[str, Any]:
        return self.dict()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OutreachPlan":
        return cls(**data)
