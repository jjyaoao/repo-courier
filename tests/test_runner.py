import json
from datetime import date, datetime

from repo_courier.config import (
    AppConfig,
    ProfileConfig,
    PushConfig,
    ReportConfig,
    RssChannelConfig,
    RssConfig,
)
from repo_courier.feeds import RssPipeline
from repo_courier.github import GitHubClient
from repo_courier.models import ChannelRun, Repository
from repo_courier.runner import run
from repo_courier.summary import Summarizer
from repo_courier.trending import TrendingClient


def _rss_config(enabled: bool = True) -> RssConfig:
    return RssConfig(
        channels={
            "news": RssChannelConfig(
                "news", "科技新闻", "repo_courier.prompts.news:build_messages", enabled
            ),
            "academic": RssChannelConfig(
                "academic",
                "学术论文",
                "repo_courier.prompts.academic:build_messages",
                enabled,
            ),
        }
    )


def test_runner_keeps_github_flow_and_writes_generic_rss_payload(tmp_path, monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 14, 9, 0, tzinfo=tz)

    repositories = [
        Repository(rank=1, owner="acme", name="css", url="https://example.com/css"),
        Repository(
            rank=8,
            owner="acme",
            name="agent",
            url="https://example.com/agent",
            topics=["agent", "mcp"],
        ),
    ]
    calls = {}
    monkeypatch.setattr(TrendingClient, "fetch", lambda self: repositories)
    monkeypatch.setattr(GitHubClient, "enrich", lambda self, items: items)
    monkeypatch.setattr("repo_courier.runner.datetime", FixedDateTime)
    monkeypatch.setattr(
        GitHubClient,
        "enrich_readmes",
        lambda self, items: calls.setdefault("readmes", [item.full_name for item in items]),
    )
    monkeypatch.setattr(Summarizer, "summarize", lambda self, items: items)
    monkeypatch.setattr(
        RssPipeline,
        "run",
        lambda self, profile, window: ChannelRun(
            self.channel.channel_id, self.channel.title, [], 0, 0
        ),
    )
    config = AppConfig(
        profile=ProfileConfig(interests=["agent", "mcp"], exclude_keywords=[], daily_picks=1),
        rss=_rss_config(),
        report=ReportConfig(
            output_dir=str(tmp_path / "reports"), data_dir=str(tmp_path / "history")
        ),
        push=PushConfig(enabled=False),
    )

    result = run(config, day=date(2026, 7, 10), dry_run=True)

    assert result.scanned_count == 2
    assert [item.full_name for item in result.repositories] == ["acme/agent"]
    assert calls["readmes"] == ["acme/agent"]
    assert list(result.rss_channels) == ["news", "academic"]
    payload = json.loads(result.report_paths["json"].read_text(encoding="utf-8"))
    assert payload["date"] == "2026-07-14"
    assert payload["rss_window"]["start"].startswith("2026-07-10T00:00:00")


def test_explicit_channels_override_disabled_config(tmp_path, monkeypatch) -> None:
    def github_must_not_run(*args, **kwargs):
        raise AssertionError("未选择 github 通道时不应运行 GitHub Trending")

    monkeypatch.setattr(TrendingClient, "fetch", github_must_not_run)
    monkeypatch.setattr(GitHubClient, "enrich", lambda self, items: items)
    monkeypatch.setattr(GitHubClient, "enrich_readmes", lambda self, items: items)
    monkeypatch.setattr(Summarizer, "summarize", lambda self, items: items)
    seen = []

    def fake_run(self, profile, window):
        seen.append((self.channel.channel_id, self.channel.enabled))
        return ChannelRun(self.channel.channel_id, self.channel.title, [], 0, 0)

    monkeypatch.setattr(RssPipeline, "run", fake_run)
    config = AppConfig(
        rss=_rss_config(enabled=False),
        report=ReportConfig(
            output_dir=str(tmp_path / "reports"), data_dir=str(tmp_path / "history")
        ),
        push=PushConfig(enabled=False),
    )

    result = run(config, day=date(2026, 7, 12), dry_run=True, channels=["news"])

    assert seen == [("news", True)]
    assert result.ran_github is False
    assert result.history_path is None


def test_explicit_github_channel_skips_all_rss(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(TrendingClient, "fetch", lambda self: [])
    monkeypatch.setattr(GitHubClient, "enrich", lambda self, items: items)
    monkeypatch.setattr(GitHubClient, "enrich_readmes", lambda self, items: items)
    monkeypatch.setattr(Summarizer, "summarize", lambda self, items: items)

    def rss_must_not_run(*args, **kwargs):
        raise AssertionError("只选择 github 通道时不应运行 RSS")

    monkeypatch.setattr(RssPipeline, "run", rss_must_not_run)
    config = AppConfig(
        rss=_rss_config(),
        report=ReportConfig(
            output_dir=str(tmp_path / "reports"), data_dir=str(tmp_path / "history")
        ),
        push=PushConfig(enabled=False),
    )

    result = run(config, day=date(2026, 7, 12), dry_run=True, channels=["github"])

    assert result.ran_github is True
    assert result.rss_channels == {}
