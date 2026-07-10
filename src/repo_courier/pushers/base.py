from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(slots=True)
class PushResult:
    channel: str
    success: bool
    detail: str = ""


class Pusher(Protocol):
    channel: str

    def send(self, title: str, content: str) -> PushResult: ...
