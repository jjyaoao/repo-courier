from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="微信公众号文章筛选与评估助手",
        focus="与关注方向的相关性、信息密度、技术深度以及时效价值",
    )
