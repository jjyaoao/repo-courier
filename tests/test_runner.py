import json
from datetime import date, datetime

from repo_courier.academic import AcademicPipeline, AcademicRun
from repo_courier.config import AcademicConfig, AppConfig, ProfileConfig, PushConfig, ReportConfig
from repo_courier.github import GitHubClient
from repo_courier.models import AcademicPaper, Repository
from repo_courier.runner import run
from repo_courier.summary import Summarizer
from repo_courier.trending import TrendingClient


def test_runner_only_reads_and_summarizes_selected_projects(tmp_path, monkeypatch) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 7, 14, 9, 0, tzinfo=tz)

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
    monkeypatch.setattr("repo_courier.runner.datetime", FixedDateTime)

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
        academic=AcademicConfig(enabled=False),
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
    assert result.history_path is not None
    assert result.history_path.name == "2026-07-14.json"
    assert result.report_paths["json"].parent.name == "2026-07-14"
    payload = json.loads(result.report_paths["json"].read_text(encoding="utf-8"))
    assert payload["date"] == "2026-07-14"
    assert payload["academic_window"]["start"].startswith("2026-07-10T00:00:00")


def test_academic_only_skips_all_github_work_and_history(tmp_path, monkeypatch) -> None:
    def github_must_not_run(*args, **kwargs):
        raise AssertionError("academic-only 模式不应调用 GitHub")

    monkeypatch.setattr(TrendingClient, "fetch", github_must_not_run)
    monkeypatch.setattr(GitHubClient, "enrich", github_must_not_run)
    paper = AcademicPaper(
        source="arxiv",
        source_id="2607.00001",
        title="Academic-only test",
        url="https://arxiv.org/abs/2607.00001",
        research_motivation="测试动机",
        core_contributions="测试贡献",
        pick_rank=1,
    )
    monkeypatch.setattr(
        AcademicPipeline,
        "run",
        lambda self, profile, window: AcademicRun([paper], 1),
    )
    config = AppConfig(
        report=ReportConfig(
            output_dir=str(tmp_path / "reports"),
            data_dir=str(tmp_path / "history"),
        ),
        push=PushConfig(enabled=False),
    )

    result = run(config, day=date(2026, 7, 12), dry_run=True, academic_only=True)

    assert result.repositories == []
    assert result.papers == [paper]
    assert result.scanned_count == 0
    assert result.history_path is None
    assert not (tmp_path / "history").exists()
    assert result.report_paths["json"].parent.name == "2026-07-12"
