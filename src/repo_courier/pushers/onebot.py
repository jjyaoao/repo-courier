from __future__ import annotations

import httpx

from .base import PushResult


class OneBotPusher:
    channel = "qq-onebot"

    def __init__(
        self,
        url: str,
        user_id: str,
        token: str = "",
        client: httpx.Client | None = None,
    ) -> None:
        self.url = url.rstrip("/")
        self.user_id = user_id
        self.token = token
        self.client = client or httpx.Client(timeout=20)

    def send(self, title: str, content: str) -> PushResult:
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        try:
            response = self.client.post(
                f"{self.url}/send_private_msg",
                headers=headers,
                json={"user_id": int(self.user_id), "message": f"{title}\n\n{content}"[:4500]},
            )
            response.raise_for_status()
            data = response.json()
            ok = data.get("status") == "ok" or data.get("retcode") == 0
            return PushResult(self.channel, ok, "ok" if ok else str(data)[:300])
        except (httpx.HTTPError, ValueError) as exc:
            return PushResult(self.channel, False, str(exc))
