from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Repository:
    rank: int
    owner: str
    name: str
    url: str
    description: str = ""
    language: str = "Unknown"
    stars: int = 0
    forks: int = 0
    stars_today: int = 0
    topics: list[str] = field(default_factory=list)
    license: str = ""
    homepage: str = ""
    open_issues: int = 0
    updated_at: str = ""
    readme_excerpt: str = ""
    summary: str = ""
    highlights: list[str] = field(default_factory=list)
    use_cases: list[str] = field(default_factory=list)
    category: str = "其他"
    risk_note: str = ""
    relevance_score: int = 0
    recommendation: str = "略过"
    why_for_you: str = ""
    matched_interests: list[str] = field(default_factory=list)
    pick_rank: int | None = None
    previous_rank: int | None = None
    is_new: bool = True

    @property
    def full_name(self) -> str:
        return f"{self.owner}/{self.name}"

    @property
    def rank_change(self) -> str:
        if self.is_new or self.previous_rank is None:
            return "NEW"
        delta = self.previous_rank - self.rank
        if delta > 0:
            return f"↑{delta}"
        if delta < 0:
            return f"↓{abs(delta)}"
        return "—"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["full_name"] = self.full_name
        data["rank_change"] = self.rank_change
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Repository:
        allowed = cls.__dataclass_fields__.keys()
        return cls(**{key: value for key, value in data.items() if key in allowed})


@dataclass(slots=True)
class AcademicPaper:
    source: str
    source_id: str
    title: str
    url: str
    abstract: str = ""
    authors: list[str] = field(default_factory=list)
    submitted_at: datetime | None = None
    introduction: str = ""
    rule_score: int = 0
    relevance_score: int = 0
    innovation_score: int = 0
    summary: str = ""
    combined_score: float = 0.0
    analysis_status: str = "pending"
    pick_rank: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["submitted_at"] = self.submitted_at.isoformat() if self.submitted_at else None
        return data


@dataclass(slots=True)
class DailyReport:
    repositories: list[Repository] = field(default_factory=list)
    papers: list[AcademicPaper] = field(default_factory=list)
    academic_window: dict[str, str] = field(default_factory=dict)
    academic_error: str = ""
