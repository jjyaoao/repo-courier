from __future__ import annotations

import httpx

from .base import PushResult


class FeishuPusher:
    channel = "feishu"

    def __init__(self, webhook: str, client: httpx.Client | None = None) -> None:
        self.webhook = webhook
        self.client = client or httpx.Client(timeout=20)

    def send(self, title: str, content: str) -> PushResult:
        try:
            response = self.client.post(
                self.webhook,
                json={
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {"tag": "plain_text", "content": title},
                            "template": "blue",
                        },
                        "elements": [{"tag": "markdown", "content": content[:18000]}],
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            ok = data.get("code", data.get("StatusCode", 0)) == 0
            return PushResult(self.channel, ok, "ok" if ok else str(data)[:300])
        except (httpx.HTTPError, ValueError) as exc:
            return PushResult(self.channel, False, str(exc))
