from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="学术论文筛选与评估助手",
        focus="研究问题、方法创新、实验或理论贡献以及对相关研究方向的价值",
    )
