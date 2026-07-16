from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="科技新闻筛选与评估助手",
        focus="事件的重要性、时效性、行业影响以及与用户关注方向的关系",
    )
