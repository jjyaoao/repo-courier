from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="大厂技术博客筛选与评估助手",
        focus="工程实践深度、架构与算法创新、可复用经验以及技术启发",
    )
