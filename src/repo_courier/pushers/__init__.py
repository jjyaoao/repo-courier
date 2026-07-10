from __future__ import annotations

from ..config import PushConfig
from .base import Pusher, PushResult
from .feishu import FeishuPusher
from .onebot import OneBotPusher
from .serverchan import ServerChanPusher
from .wecom import WeComPusher


def configured_pushers(config: PushConfig) -> list[Pusher]:
    pushers: list[Pusher] = []
    if config.feishu_webhook:
        pushers.append(FeishuPusher(config.feishu_webhook))
    if config.wecom_webhook:
        pushers.append(WeComPusher(config.wecom_webhook))
    if config.serverchan_sendkey:
        pushers.append(ServerChanPusher(config.serverchan_sendkey))
    if config.onebot_url and config.onebot_user_id:
        pushers.append(OneBotPusher(config.onebot_url, config.onebot_user_id, config.onebot_token))
    return pushers


__all__ = ["Pusher", "PushResult", "configured_pushers"]
