from __future__ import annotations

import httpx

from .base import PushResult


class ServerChanPusher:
    channel = "serverchan"

    def __init__(self, sendkey: str, client: httpx.Client | None = None) -> None:
        self.sendkey = sendkey
        self.client = client or httpx.Client(timeout=20)

    def send(self, title: str, content: str) -> PushResult:
        try:
            response = self.client.post(
                f"https://sctapi.ftqq.com/{self.sendkey}.send",
                data={"title": title[:32], "desp": content[:30000]},
            )
            response.raise_for_status()
            data = response.json()
            code = data.get("code", data.get("errno", -1))
            ok = code == 0
            return PushResult(self.channel, ok, "ok" if ok else str(data)[:300])
        except (httpx.HTTPError, ValueError) as exc:
            return PushResult(self.channel, False, str(exc))
