import asyncio
import json
import time
from datetime import datetime, timezone
from types import SimpleNamespace

import httpx

from repo_courier import web
from repo_courier.config import (
    AppConfig,
    RssChannelConfig,
    RssConfig,
    RssSourceConfig,
    WechatAccountConfig,
    WechatConfig,
)
from repo_courier.models import ChannelRun, Repository, RssItem


def request(app, method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def config_with_news() -> AppConfig:
    return AppConfig(
        rss=RssConfig(
            channels={
                "news": RssChannelConfig(
                    "news",
                    "科技新闻",
                    "repo_courier.prompts.news:build_messages",
                    sources=[RssSourceConfig("wired", "WIRED", "https://example.com/rss")],
                )
            }
        )
    )


def test_preview_request_cleans_interests_and_sources() -> None:
    payload = web.PreviewRequest(
        interests=[" Agent ", "agent", "developer   tools"],
        sources=[" GitHub ", "news", "news"],
    )

    assert payload.interests == ["Agent", "developer tools"]
    assert payload.sources == ["github", "news"]


def test_source_options_follow_configured_rss_channels() -> None:
    options = web.source_options(config_with_news())

    assert [option["id"] for option in options] == ["github", "news"]
    assert options[0]["default"] is True
    assert options[1]["source_count"] == 1


def test_source_options_include_wechat_only_when_accounts_are_configured() -> None:
    config = config_with_news()
    assert "wechat" not in [option["id"] for option in web.source_options(config)]

    config.wechat = WechatConfig(accounts=[WechatAccountConfig("Account", "fake-1")])
    options = web.source_options(config)

    assert [option["id"] for option in options] == ["github", "news", "wechat"]
    assert options[-1]["source_count"] == 1


def test_generate_preview_uses_request_scoped_config(monkeypatch) -> None:
    captured = {}

    def fake_run(config, **kwargs):
        captured["config"] = config
        captured["kwargs"] = kwargs
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
            analysis_status="fallback",
            pick_rank=1,
        )
        return SimpleNamespace(repositories=[repository], rss_channels={}, scanned_count=20)

    monkeypatch.setattr(web, "load_web_config", config_with_news)
    monkeypatch.setattr(web, "run", fake_run)

    result = web.generate_preview(
        web.PreviewRequest(
            interests=["agent"],
            sources=["github"],
            github_token="github-secret",
        )
    )

    config = captured["config"]
    assert config.profile.interests == ["agent"]
    assert config.profile.daily_picks == 3
    assert config.github.token == "github-secret"
    assert config.repo_llm.enabled is False
    assert config.repo_llm.api_key == ""
    assert config.push.enabled is False
    assert captured["kwargs"] == {"dry_run": True, "channels": ["github"]}
    assert result["repositories"][0]["full_name"] == "acme/agent-kit"
    assert result["repositories"][0]["analysis_status"] == "fallback"
    assert result["channels"] == []
    assert result["used_ai"] is False


def test_generate_preview_serializes_rss_channels(monkeypatch) -> None:
    item = RssItem(
        channel_id="news",
        source_id="wired",
        source_name="WIRED",
        entry_id="entry",
        title="Agent news",
        url="https://example.com/news",
        summary="新闻摘要",
        recommendation_reason="命中 agent",
        published_at=datetime(2026, 7, 15, tzinfo=timezone.utc),
        relevance_score=8,
        innovation_score=7,
        analysis_status="ai",
        pick_rank=1,
    )
    channel = ChannelRun("news", "科技新闻", [item], 12, 4)

    monkeypatch.setattr(web, "load_web_config", config_with_news)
    monkeypatch.setattr(
        web,
        "run",
        lambda config, **kwargs: SimpleNamespace(
            repositories=[], rss_channels={"news": channel}, scanned_count=0
        ),
    )

    result = web.generate_preview(
        web.PreviewRequest(
            interests=["agent"],
            sources=["news"],
            ai_model="model",
            ai_api_key="secret",
        )
    )

    assert result["rss_scanned_count"] == 12
    assert result["channels"][0]["id"] == "news"
    assert result["channels"][0]["items"][0]["source_name"] == "WIRED"
    assert result["used_ai"] is True


def test_unknown_source_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(web, "load_web_config", config_with_news)
    payload = web.PreviewRequest(interests=["agent"], sources=["unknown"])

    try:
        web.generate_preview(payload)
    except ValueError as exc:
        assert "未知内容频道" in str(exc)
    else:
        raise AssertionError("未配置的频道应被拒绝")


def test_ai_base_url_must_be_explicitly_allowed(monkeypatch) -> None:
    monkeypatch.delenv("REPO_COURIER_ALLOWED_AI_BASE_URLS", raising=False)
    payload = web.PreviewRequest(
        interests=["agent"],
        ai_base_url="https://internal.example/v1/chat/completions",
        ai_model="model",
        ai_api_key="secret",
    )

    try:
        web.validate_ai_settings(payload)
    except ValueError as exc:
        assert "未被当前站点允许" in str(exc)
    else:
        raise AssertionError("未在白名单中的模型地址应被拒绝")


def test_ai_base_url_accepts_root_and_normalizes_endpoint(monkeypatch) -> None:
    monkeypatch.setenv(
        "REPO_COURIER_ALLOWED_AI_BASE_URLS",
        "https://compatible.example/v1",
    )
    payload = web.PreviewRequest(
        interests=["agent"],
        ai_base_url="https://compatible.example/v1",
        ai_model="compatible-model",
        ai_api_key="secret",
    )

    endpoint, model, key = web.validate_ai_settings(payload)

    assert endpoint == "https://compatible.example/v1/chat/completions"
    assert model == "compatible-model"
    assert key == "secret"


def test_ai_base_url_accepts_full_endpoint_from_root_allowlist(monkeypatch) -> None:
    monkeypatch.setenv(
        "REPO_COURIER_ALLOWED_AI_BASE_URLS",
        "https://compatible.example/api/v1",
    )
    payload = web.PreviewRequest(
        interests=["agent"],
        ai_base_url="https://compatible.example/api/v1/chat/completions",
        ai_model="compatible-model",
        ai_api_key="secret",
    )

    endpoint, _, _ = web.validate_ai_settings(payload)

    assert endpoint == "https://compatible.example/api/v1/chat/completions"


def test_preview_api_does_not_echo_secrets(monkeypatch) -> None:
    captured = {}

    def fake_preview(payload):
        captured["ai"] = payload.ai_api_key.get_secret_value()
        captured["github"] = payload.github_token.get_secret_value()
        return {
            "scanned_count": 20,
            "rss_scanned_count": 0,
            "repositories": [],
            "channels": [],
            "sources": ["github"],
            "used_ai": True,
        }

    monkeypatch.setattr(web, "generate_preview", fake_preview)
    response = request(
        web.create_app(),
        "POST",
        "/api/preview",
        json={
            "interests": ["agent"],
            "github_token": "github-secret",
            "ai_model": "model",
            "ai_api_key": "top-secret",
        },
    )

    assert response.status_code == 200
    assert captured == {"ai": "top-secret", "github": "github-secret"}
    assert "top-secret" not in response.text
    assert "github-secret" not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_stream_preview_emits_channel_results_and_isolates_failures(monkeypatch) -> None:
    monkeypatch.setattr(web, "load_web_config", config_with_news)

    def fake_preview(payload):
        source = payload.sources[0]
        if source == "news":
            raise RuntimeError("private failure detail")
        return {
            "scanned_count": 20,
            "rss_scanned_count": 0,
            "repositories": [{"full_name": "acme/agent-kit"}],
            "channels": [],
            "sources": [source],
            "used_ai": False,
        }

    monkeypatch.setattr(web, "generate_preview", fake_preview)
    response = request(
        web.create_app(),
        "POST",
        "/api/preview/stream",
        json={"interests": ["agent"], "sources": ["github", "news"]},
    )
    events = [json.loads(line) for line in response.text.splitlines() if line]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert events[0]["type"] == "start"
    assert {event["source"] for event in events if event["type"] == "channel_started"} == {
        "github",
        "news",
    }
    completed = [event for event in events if event["type"] == "channel_complete"]
    assert completed[0]["source"] == "github"
    assert completed[0]["result"]["repositories"][0]["full_name"] == "acme/agent-kit"
    errors = [event for event in events if event["type"] == "channel_error"]
    assert errors == [
        {
            "type": "channel_error",
            "source": "news",
            "title": "科技新闻",
            "message": "该频道暂时不可用",
        }
    ]
    assert events[-1] == {"type": "complete", "total": 2, "completed": 1, "failed": 1}
    assert "private failure detail" not in response.text


def test_stream_preview_times_out_slow_channel(monkeypatch) -> None:
    monkeypatch.setattr(web, "load_web_config", config_with_news)

    def slow_preview(payload):
        del payload
        time.sleep(0.05)
        return {}

    monkeypatch.setattr(web, "generate_preview", slow_preview)
    app = web.create_app()
    app.state.preview_channel_timeout = 0.01
    response = request(
        app,
        "POST",
        "/api/preview/stream",
        json={"interests": ["agent"], "sources": ["news"]},
    )
    events = [json.loads(line) for line in response.text.splitlines() if line]

    assert [event["type"] for event in events] == [
        "start",
        "channel_started",
        "channel_error",
        "complete",
    ]
    assert events[2]["message"] == "该频道处理超时"
    assert events[-1]["failed"] == 1


def test_web_home_health_and_options_are_available() -> None:
    app = web.create_app()
    home = request(app, "GET", "/")
    health = request(app, "GET", "/health")
    options = request(app, "GET", "/api/options")

    assert home.status_code == 200
    assert "多个技术频道" in home.text
    assert health.json() == {"status": "ok"}
    assert {source["id"] for source in options.json()["sources"]} == {
        "github",
        "news",
        "blogs",
        "academic",
            "products",
            "security",
            "wechat",
        }


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


def test_web_validation_errors_do_not_echo_secret_fields() -> None:
    github_secret = "github-secret-" + "x" * 500
    ai_secret = "ai-secret-" + "x" * 500
    response = request(
        web.create_app(),
        "POST",
        "/api/preview",
        json={
            "interests": ["agent"],
            "github_token": github_secret,
            "ai_api_key": ai_secret,
            "ai_model": "model",
        },
    )

    assert response.status_code == 422
    assert github_secret not in response.text
    assert ai_secret not in response.text
    assert '"input"' not in response.text
