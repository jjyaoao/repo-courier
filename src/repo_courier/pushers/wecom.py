from __future__ import annotations

import httpx

from .base import PushResult


class WeComPusher:
    channel = "wecom"

    def __init__(self, webhook: str, client: httpx.Client | None = None) -> None:
        self.webhook = webhook
        self.client = client or httpx.Client(timeout=20)

    def send(self, title: str, content: str) -> PushResult:
        try:
            response = self.client.post(
                self.webhook,
                json={
                    "msgtype": "markdown",
                    "markdown": {"content": f"# {title}\n{content}"[:4000]},
                },
            )
            response.raise_for_status()
            data = response.json()
            ok = data.get("errcode") == 0
            return PushResult(self.channel, ok, "ok" if ok else str(data)[:300])
        except (httpx.HTTPError, ValueError) as exc:
            return PushResult(self.channel, False, str(exc))
