from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import AppConfig
from .github import GitHubClient
from .models import Repository
from .personalize import Personalizer
from .pushers import PushResult, configured_pushers
from .report import ReportWriter
from .storage import HistoryStore
from .summary import Summarizer
from .trending import TrendingClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class RunResult:
    repositories: list[Repository]
    scanned_count: int
    report_paths: dict[str, Path]
    history_path: Path
    push_results: list[PushResult]


def run(config: AppConfig, *, day: date | None = None, dry_run: bool = False) -> RunResult:
    report_day = day or date.today()
    logger.info("正在获取 GitHub Trending")
    repositories = TrendingClient(config.github).fetch()
    logger.info("已获取 %d 个项目，正在补充 GitHub 元数据", len(repositories))
    github = GitHubClient(config.github)
    github.enrich(repositories)

    history = HistoryStore(config.report.data_dir)
    history.apply_rank_history(repositories, report_day)
    picks = Personalizer(config.profile).select(repositories)
    github.enrich_readmes(picks)
    Summarizer(config.summary).summarize(picks)

    writer = ReportWriter(config.report)
    report_paths = writer.write(picks, report_day)
    history_path = history.save(repositories, report_day)
    logger.info("报告已生成: %s", report_paths["markdown"])

    push_results: list[PushResult] = []
    if config.push.enabled and not dry_run and picks:
        title = f"GitHub Trending 日报 · {report_day.isoformat()}"
        digest = writer.digest(picks, report_day, limit=config.profile.daily_picks)
        for pusher in configured_pushers(config.push):
            result = pusher.send(title, digest)
            push_results.append(result)
            log = logger.info if result.success else logger.error
            log("推送通道 %s: %s", result.channel, result.detail)
    elif config.push.enabled and not dry_run:
        logger.info("今天没有达到推荐条件的项目，跳过推送")
    return RunResult(picks, len(repositories), report_paths, history_path, push_results)
