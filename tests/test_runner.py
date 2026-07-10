from datetime import date

from repo_courier.config import AppConfig, ProfileConfig, PushConfig, ReportConfig
from repo_courier.github import GitHubClient
from repo_courier.models import Repository
from repo_courier.runner import run
from repo_courier.summary import Summarizer
from repo_courier.trending import TrendingClient


def test_runner_only_reads_and_summarizes_selected_projects(tmp_path, monkeypatch) -> None:
    repositories = [
        Repository(
            rank=1,
            owner="acme",
            name="css-gallery",
            url="https://example.com/css",
            stars_today=1_000,
        ),
        Repository(
            rank=8,
            owner="acme",
            name="agent-runner",
            url="https://example.com/agent",
            topics=["agent", "mcp"],
            stars_today=100,
        ),
    ]
    calls: dict[str, list[str]] = {}

    monkeypatch.setattr(TrendingClient, "fetch", lambda self: repositories)
    monkeypatch.setattr(GitHubClient, "enrich", lambda self, items: items)

    def readmes(self, items):
        calls["readmes"] = [item.full_name for item in items]

    def summaries(self, items):
        calls["summaries"] = [item.full_name for item in items]
        for item in items:
            item.summary = item.description or item.full_name
        return items

    monkeypatch.setattr(GitHubClient, "enrich_readmes", readmes)
    monkeypatch.setattr(Summarizer, "summarize", summaries)
    config = AppConfig(
        profile=ProfileConfig(interests=["agent", "mcp"], exclude_keywords=[], daily_picks=1),
        report=ReportConfig(
            output_dir=str(tmp_path / "reports"), data_dir=str(tmp_path / "history")
        ),
        push=PushConfig(enabled=False),
    )

    result = run(config, day=date(2026, 7, 10), dry_run=True)

    assert result.scanned_count == 2
    assert [item.full_name for item in result.repositories] == ["acme/agent-runner"]
    assert calls["readmes"] == ["acme/agent-runner"]
    assert calls["summaries"] == ["acme/agent-runner"]
