from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from .models import Repository


class HistoryStore:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)

    def apply_rank_history(self, repositories: list[Repository], day: date) -> None:
        previous_file = self._previous_file(day)
        if previous_file is None:
            return
        try:
            payload = json.loads(previous_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        previous = {
            item.get("full_name") or f"{item.get('owner')}/{item.get('name')}": item.get("rank")
            for item in payload.get("repositories", [])
            if isinstance(item, dict)
        }
        for repository in repositories:
            if repository.full_name in previous:
                repository.previous_rank = int(previous[repository.full_name])
                repository.is_new = False

    def save(self, repositories: list[Repository], day: date) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{day.isoformat()}.json"
        payload = {
            "date": day.isoformat(),
            "repositories": [repository.to_dict() for repository in repositories],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def _previous_file(self, day: date) -> Path | None:
        if not self.directory.exists():
            return None
        candidates = sorted(
            path for path in self.directory.glob("*.json") if path.stem < day.isoformat()
        )
        return candidates[-1] if candidates else None
