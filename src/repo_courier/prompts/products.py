from __future__ import annotations

from ..config import ProfileConfig
from ..models import RssItem
from .common import build_messages as build_common_messages


def build_messages(item: RssItem, profile: ProfileConfig) -> list[dict[str, str]]:
    return build_common_messages(
        item,
        profile,
        role="开发者产品更新筛选与评估助手",
        focus="新增能力、行为变化、兼容性影响以及对开发者工作流的实际价值",
    )
