"""Channel-neutral message models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class IncomingMessage:
    channel: str
    user_key: str
    text: str | None
    attachments: list[dict[str, Any]] = field(default_factory=list)
    message_id: str | None = None
    timestamp: datetime | None = None


@dataclass(frozen=True)
class OutgoingMessage:
    user_key: str
    parts: list[str]
    buttons: list[dict[str, Any]] | None = None
