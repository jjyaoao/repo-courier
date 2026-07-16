from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="安全资讯筛选与评估助手",
        focus="风险严重性、利用条件、影响范围、防护建议以及对用户技术栈的相关性",
    )
