from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .academic import AcademicPipeline
from .academic.base import BEIJING, SearchWindow
from .config import AppConfig
from .feeds import TechBlogPipeline, TechNewsPipeline
from .github import GitHubClient
from .models import AcademicPaper, DailyReport, Repository, TechBlogPost, TechNewsPost
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
    tech_blogs: list[TechBlogPost]
    tech_news: list[TechNewsPost]
    scanned_count: int
    academic_scanned_count: int
    tech_blog_scanned_count: int
    tech_news_scanned_count: int
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
    today = datetime.now(BEIJING).date()
    academic_day = day or (today - timedelta(days=1))
    # Trending is a live snapshot and must always be stored under the day on
    # which it was fetched. Academic-only backfills keep their requested day.
    report_day = academic_day if academic_only else today
    repositories: list[Repository] = []
    picks: list[Repository] = []
    history_path: Path | None = None
    if academic_only:
        logger.info("Academic-only 模式：跳过 GitHub、Tech Blog、Tech News 和历史读写")
    else:
        logger.info("正在获取 GitHub Trending")
        repositories = TrendingClient(config.github).fetch()
        logger.info("已获取 %d 个项目，正在补充 GitHub 元数据", len(repositories))
        github = GitHubClient(config.github)
        github.enrich(repositories)

        history = HistoryStore(config.report.data_dir)
        history.apply_rank_history(repositories, today)
        picks = Personalizer(config.profile).select(repositories)
        github.enrich_readmes(picks)
        Summarizer(config.summary).summarize(picks)
        history_path = history.save(repositories, today)

    window = SearchWindow.for_beijing_day(academic_day)
    academic_error = ""
    academic_scanned_count = 0
    papers: list[AcademicPaper] = []
    try:
        logger.info("正在获取 %s 的学术论文", academic_day.isoformat())
        academic_run = AcademicPipeline(config.academic, config.summary).run(config.profile, window)
        papers = academic_run.papers
        academic_scanned_count = academic_run.scanned_count
    except Exception as exc:  # Academic is intentionally isolated from the GitHub report.
        academic_error = str(exc)
        logger.exception("Academic 流水线失败，继续生成 GitHub 报告: %s", exc)

    tech_blogs: list[TechBlogPost] = []
    tech_news: list[TechNewsPost] = []
    tech_blog_errors: dict[str, str] = {}
    tech_news_errors: dict[str, str] = {}
    tech_blog_scanned_count = 0
    tech_news_scanned_count = 0
    if not academic_only:
        try:
            blog_run = TechBlogPipeline(
                config.tech_blog, config.academic, config.summary
            ).run(config.profile, window)
            tech_blogs = blog_run.posts
            tech_blog_scanned_count = blog_run.scanned_count
            tech_blog_errors = blog_run.errors
        except Exception as exc:  # Keep every report category independently available.
            tech_blog_errors["pipeline"] = str(exc)
            logger.exception("Tech Blog 流水线失败，继续生成其他类别: %s", exc)
        try:
            news_run = TechNewsPipeline(
                config.tech_news, config.academic, config.summary
            ).run(config.profile, window)
            tech_news = news_run.posts
            tech_news_scanned_count = news_run.scanned_count
            tech_news_errors = news_run.errors
        except Exception as exc:
            tech_news_errors["pipeline"] = str(exc)
            logger.exception("Tech News 流水线失败，继续生成其他类别: %s", exc)

    # A technical feed wins when an official source publishes the exact same URL in both groups.
    blog_urls = {item.url for item in tech_blogs}
    tech_news = [item for item in tech_news if item.url not in blog_urls]
    for rank, post in enumerate(tech_news, start=1):
        post.pick_rank = rank

    writer = ReportWriter(config.report)
    daily = DailyReport(
        repositories=picks,
        papers=papers,
        tech_blogs=tech_blogs,
        tech_news=tech_news,
        academic_window=window.to_dict(),
        academic_error=academic_error,
        tech_blog_errors=tech_blog_errors,
        tech_news_errors=tech_news_errors,
    )
    report_paths = writer.write(daily, report_day)
    logger.info("报告已生成: %s", report_paths["markdown"])

    push_results: list[PushResult] = []
    if config.push.enabled and not dry_run and (picks or papers or tech_blogs or tech_news):
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
        repositories=picks,
        papers=papers,
        tech_blogs=tech_blogs,
        tech_news=tech_news,
        scanned_count=len(repositories),
        academic_scanned_count=academic_scanned_count,
        tech_blog_scanned_count=tech_blog_scanned_count,
        tech_news_scanned_count=tech_news_scanned_count,
        report_paths=report_paths,
        history_path=history_path,
        push_results=push_results,
    )
