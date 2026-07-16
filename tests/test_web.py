import asyncio
from types import SimpleNamespace

import httpx

from repo_courier import web
from repo_courier.models import Repository


def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_preview_request_cleans_and_deduplicates_interests() -> None:
    payload = web.PreviewRequest(interests=[" Agent ", "agent", "developer   tools"])

    assert payload.interests == ["Agent", "developer tools"]


def test_generate_preview_uses_request_scoped_config(tmp_path, monkeypatch) -> None:
    captured = {}

    def fake_run(config, **kwargs):
        captured["config"] = config
        captured["kwargs"] = kwargs
        assert tmp_path != config.report.output_dir
        repository = Repository(
            rank=2,
            owner="acme",
            name="agent-kit",
            url="https://github.com/acme/agent-kit",
            stars=1_200,
            stars_today=240,
            relevance_score=72,
            recommendation="深挖",
            why_for_you="命中 agent",
            pick_rank=1,
        )
        return SimpleNamespace(repositories=[repository], scanned_count=20)

    monkeypatch.setenv("REPO_COURIER_CONFIG", str(tmp_path / "missing.yaml"))
    monkeypatch.setattr(web, "run", fake_run)

    result = web.generate_preview(web.PreviewRequest(interests=["agent"]))

    config = captured["config"]
    assert config.profile.interests == ["agent"]
    assert config.profile.daily_picks == 3
    assert config.repo_llm.enabled is False
    assert config.repo_llm.api_key == ""
    assert all(not channel.enabled for channel in config.rss.channels.values())
    assert config.push.enabled is False
    assert captured["kwargs"] == {"dry_run": True}
    assert result["repositories"][0]["full_name"] == "acme/agent-kit"
    assert result["used_ai"] is False


def test_ai_base_url_must_be_explicitly_allowed(monkeypatch) -> None:
    monkeypatch.delenv("REPO_COURIER_ALLOWED_AI_BASE_URLS", raising=False)
    payload = web.PreviewRequest(
        interests=["agent"],
        ai_base_url="https://internal.example/v1",
        ai_model="model",
        ai_api_key="secret",
    )

    try:
        web.validate_ai_settings(payload)
    except ValueError as exc:
        assert "未被当前站点允许" in str(exc)
    else:
        raise AssertionError("未在白名单中的模型地址应被拒绝")


def test_preview_api_does_not_echo_secret(monkeypatch) -> None:
    captured = {}

    def fake_preview(payload):
        captured["secret"] = payload.ai_api_key.get_secret_value()
        return {"scanned_count": 20, "repositories": [], "used_ai": True}

    monkeypatch.setattr(web, "generate_preview", fake_preview)
    response = request(
        web.create_app(),
        "POST",
        "/api/preview",
        json={
            "interests": ["agent"],
            "ai_model": "model",
            "ai_api_key": "top-secret",
        },
    )

    assert response.status_code == 200
    assert captured["secret"] == "top-secret"
    assert "top-secret" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-frame-options"] == "DENY"


def test_web_home_and_health_are_available() -> None:
    app = web.create_app()
    home = request(app, "GET", "/")
    health = request(app, "GET", "/health")

    assert home.status_code == 200
    assert "今天的 GitHub Trending" in home.text
    assert health.json() == {"status": "ok"}


def test_web_rejects_oversized_requests_without_echoing_content() -> None:
    secret = "secret-that-must-not-be-echoed"
    response = request(
        web.create_app(),
        "POST",
        "/api/preview",
        content=(secret + "x" * web.MAX_REQUEST_BYTES),
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert secret not in response.text
