from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..config import AcademicConfig, ProfileConfig, SummaryConfig
from ..models import AcademicPaper
from .analyzer import PaperAnalyzer
from .arxiv import ArxivSource
from .base import SearchWindow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AcademicRun:
    papers: list[AcademicPaper]
    scanned_count: int


class AcademicPipeline:
    def __init__(
        self,
        config: AcademicConfig,
        summary: SummaryConfig,
        *,
        source: ArxivSource | None = None,
        analyzer: PaperAnalyzer | None = None,
    ) -> None:
        self.config = config
        self.source = source or ArxivSource(config.arxiv)
        self.analyzer = analyzer or PaperAnalyzer(config, summary)

    def run(self, profile: ProfileConfig, window: SearchWindow) -> AcademicRun:
        if not self.config.enabled or not self.config.arxiv.enabled:
            logger.info("[Academic] Academic 或 ArXiv 已关闭，跳过学术检索")
            return AcademicRun([], 0)
        candidates = self.source.fetch(profile, window)
        logger.info("[Academic] 阶段 2/4：对 %d 篇候选论文计算规则分", len(candidates))
        for paper in candidates:
            paper.rule_score = rule_score(paper, profile)
        shortlist_size = max(1, self.config.arxiv.final_picks) * 2
        shortlist = sorted(
            candidates,
            key=lambda item: (
                -item.rule_score,
                -(item.submitted_at.timestamp() if item.submitted_at else 0),
            ),
        )[:shortlist_size]
        logger.info(
            "[Academic] 阶段 2/4 完成：规则初筛 %d 篇（final_picks=%d 的 2 倍）",
            len(shortlist),
            self.config.arxiv.final_picks,
        )
        workers = analysis_worker_count(
            self.config.arxiv.final_picks,
            self.config.arxiv.max_analysis_workers,
            len(shortlist),
        )
        logger.info(
            "[Academic] 阶段 3/4：使用 %d 个并发任务提取 Introduction 并调用 LLM（上限=%d）",
            workers,
            self.config.arxiv.max_analysis_workers,
        )

        def enrich_and_analyze(paper: AcademicPaper) -> None:
            self.source.enrich_introduction(paper)
            self.analyzer.analyze(paper, profile)
            paper.combined_score = round(
                0.4 * paper.rule_score
                + 0.6 * (paper.relevance_score + paper.innovation_score),
                2,
            )

        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(enrich_and_analyze, shortlist))
        logger.info("[Academic] 阶段 3/4 完成：%d 篇论文分析结束", len(shortlist))
        picks = sorted(
            shortlist,
            key=lambda item: (-item.combined_score, -item.rule_score, item.title.lower()),
        )[: max(1, self.config.arxiv.final_picks)]
        for rank, paper in enumerate(picks, start=1):
            paper.pick_rank = rank
            logger.info(
                "[Academic/Rank] #%d %s 综合分=%.2f（相关性=%d，创新性=%d，规则分=%d）",
                rank,
                paper.source_id,
                paper.combined_score,
                paper.relevance_score,
                paper.innovation_score,
                paper.rule_score,
            )
        logger.info("[Academic] 阶段 4/4 完成：最终选出 %d 篇论文", len(picks))
        return AcademicRun(picks, len(candidates))


def rule_score(paper: AcademicPaper, profile: ProfileConfig) -> int:
    title = _normalize(paper.title)
    abstract = _normalize(paper.abstract)
    score = 0
    for keyword in profile.interests:
        term = _normalize(keyword)
        score += 3 * _count(title, term) + _count(abstract, term)
    for keyword in profile.exclude_keywords:
        term = _normalize(keyword)
        score -= 3 * _count(title, term) + _count(abstract, term)
    return score


def analysis_worker_count(final_picks: int, max_workers: int, shortlist_count: int) -> int:
    return max(1, min(2 * final_picks, max_workers, shortlist_count or 1))


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", value.lower()).strip()


def _count(text: str, term: str) -> int:
    if not term:
        return 0
    return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
