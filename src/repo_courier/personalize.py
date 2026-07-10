from __future__ import annotations

import re

from .config import ProfileConfig
from .models import Repository


class Personalizer:
    """Rank Trending repositories against a small, explicit interest profile."""

    def __init__(self, config: ProfileConfig) -> None:
        self.config = config

    def select(self, repositories: list[Repository]) -> list[Repository]:
        for repository in repositories:
            self._score(repository)
        ranked = sorted(repositories, key=lambda item: (-item.relevance_score, item.rank))
        picks = [item for item in ranked if item.recommendation != "略过"][
            : max(1, self.config.daily_picks)
        ]
        for index, repository in enumerate(picks, start=1):
            repository.pick_rank = index
        return picks

    def _score(self, repository: Repository) -> None:
        name_topics = _normalize(" ".join([repository.name, *repository.topics]))
        description = _normalize(repository.description)
        readme = _normalize(repository.readme_excerpt[:3000])
        matched: list[str] = []
        score = 0

        for interest in self.config.interests:
            terms = _interest_terms(interest)
            if any(_contains(name_topics, term) for term in terms):
                score += 30
                matched.append(interest)
            elif any(_contains(description, term) for term in terms):
                score += 20
                matched.append(interest)
            elif any(_contains(readme, term) for term in terms):
                score += 8
                matched.append(interest)

        excluded = [
            keyword
            for keyword in self.config.exclude_keywords
            if _contains(" ".join([name_topics, description, readme]), _normalize(keyword))
        ]
        if excluded:
            score -= 35

        # Popularity is only a tie-breaker: relevance remains the primary signal.
        score += min(20, repository.stars_today // 50)
        score += max(0, 6 - min(repository.rank, 6))
        if repository.license:
            score += 5
        repository.relevance_score = max(0, min(100, score))
        repository.matched_interests = list(dict.fromkeys(matched))
        repository.recommendation = _recommendation(
            repository.relevance_score, bool(repository.matched_interests), bool(excluded)
        )
        repository.why_for_you = _reason(repository, excluded)


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value.lower()).strip()


def _interest_terms(interest: str) -> list[str]:
    normalized = _normalize(interest)
    terms = [normalized]
    terms.extend(part for part in normalized.split() if len(part) >= 2)
    return list(dict.fromkeys(term for term in terms if term))


def _contains(text: str, term: str) -> bool:
    if not term:
        return False
    return f" {term} " in f" {text} " or term in text.split()


def _recommendation(score: int, has_match: bool, excluded: bool) -> str:
    if excluded or not has_match:
        return "略过"
    if score >= 50:
        return "深挖"
    if score >= 20:
        return "关注"
    return "略过"


def _reason(repository: Repository, excluded: list[str]) -> str:
    if excluded:
        matched = "、".join(repository.matched_interests[:2])
        context = f"；虽命中 {matched}" if matched else ""
        return f"命中过滤词：{'、'.join(excluded[:2])}{context}，仍降低推荐。"
    if repository.matched_interests:
        matched = "、".join(repository.matched_interests[:3])
        return f"命中你的关注词：{matched}；今日新增约 {repository.stars_today:,} Stars。"
    return f"与关注词匹配较弱；因 Trending 排名第 {repository.rank} 暂时保留观察。"
