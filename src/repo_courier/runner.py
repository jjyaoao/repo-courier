from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .academic import AcademicPipeline
from .academic.base import BEIJING, SearchWindow
from .config import AppConfig
from .github import GitHubClient
from .models import AcademicPaper, DailyReport, Repository
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
    papers: list[AcademicPaper]
    scanned_count: int
    academic_scanned_count: int
    report_paths: dict[str, Path]
    history_path: Path | None
    push_results: list[PushResult]


def run(
    config: AppConfig,
    *,
    day: date | None = None,
    dry_run: bool = False,
    academic_only: bool = False,
) -> RunResult:
    report_day = day or (datetime.now(BEIJING).date() - timedelta(days=1))
    repositories: list[Repository] = []
    picks: list[Repository] = []
    history_path: Path | None = None
    if academic_only:
        logger.info("Academic-only 模式：跳过 GitHub Trending、API、摘要和历史读写")
    else:
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
        history_path = history.save(repositories, report_day)

    window = SearchWindow.for_beijing_day(report_day)
    academic_error = ""
    academic_scanned_count = 0
    papers: list[AcademicPaper] = []
    try:
        logger.info("正在获取 %s 的学术论文", report_day.isoformat())
        academic_run = AcademicPipeline(config.academic, config.summary).run(config.profile, window)
        papers = academic_run.papers
        academic_scanned_count = academic_run.scanned_count
    except Exception as exc:  # Academic is intentionally isolated from the GitHub report.
        academic_error = str(exc)
        logger.exception("Academic 流水线失败，继续生成 GitHub 报告: %s", exc)

    writer = ReportWriter(config.report)
    daily = DailyReport(
        repositories=picks,
        papers=papers,
        academic_window=window.to_dict(),
        academic_error=academic_error,
    )
    report_paths = writer.write(daily, report_day)
    logger.info("报告已生成: %s", report_paths["markdown"])

    push_results: list[PushResult] = []
    if config.push.enabled and not dry_run and (picks or papers):
        title = f"RepoCourier 日报 · {report_day.isoformat()}"
        digest = writer.digest(daily, report_day, limit=config.profile.daily_picks)
        for pusher in configured_pushers(config.push):
            result = pusher.send(title, digest)
            push_results.append(result)
            log = logger.info if result.success else logger.error
            log("推送通道 %s: %s", result.channel, result.detail)
    elif config.push.enabled and not dry_run:
        logger.info("今天没有达到推荐条件的项目，跳过推送")
    return RunResult(
        picks,
        papers,
        len(repositories),
        academic_scanned_count,
        report_paths,
        history_path,
        push_results,
    )
