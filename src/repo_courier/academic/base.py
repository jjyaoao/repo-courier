from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from typing import Protocol
from zoneinfo import ZoneInfo

from ..config import ProfileConfig
from ..models import AcademicPaper

BEIJING = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True, slots=True)
class SearchWindow:
    start: datetime
    end: datetime

    @classmethod
    def for_beijing_day(cls, day: date) -> SearchWindow:
        return cls(
            datetime.combine(day, time.min, tzinfo=BEIJING),
            datetime.combine(day, time.max.replace(microsecond=0), tzinfo=BEIJING),
        )

    @property
    def start_utc(self) -> datetime:
        return self.start.astimezone(timezone.utc)

    @property
    def end_utc(self) -> datetime:
        return self.end.astimezone(timezone.utc)

    def contains(self, value: datetime) -> bool:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return self.start_utc <= value.astimezone(timezone.utc) <= self.end_utc

    def to_dict(self) -> dict[str, str]:
        return {
            "timezone": "Asia/Shanghai",
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
        }


class AcademicSource(Protocol):
    def fetch(self, profile: ProfileConfig, window: SearchWindow) -> list[AcademicPaper]: ...
