from __future__ import annotations

import logging
import re
import time
import xml.etree.ElementTree as ET
from collections.abc import Callable
from datetime import datetime

import httpx
from bs4 import BeautifulSoup, Tag

from ..config import ArxivConfig, ProfileConfig
from ..models import AcademicPaper
from .base import SearchWindow

logger = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
USER_AGENT = "RepoCourier/0.1 (academic paper discovery)"


class ArxivSource:
    def __init__(
        self,
        config: ArxivConfig,
        client: httpx.Client | None = None,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.sleeper = sleeper
        self.client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    def fetch(self, profile: ProfileConfig, window: SearchWindow) -> list[AcademicPaper]:
        if not profile.interests:
            logger.warning("[Academic/ArXiv] profile.interests 为空，跳过检索")
            return []
        query = build_query(profile, window)
        logger.info(
            "[Academic/ArXiv] 阶段 1/4：开始检索；北京时间窗口=%s 至 %s",
            window.start.isoformat(),
            window.end.isoformat(),
        )
        papers: list[AcademicPaper] = []
        offset = 0
        page_number = 0
        while offset < self.config.candidate_limit:
            if page_number:
                logger.info(
                    "[Academic/ArXiv] 等待 %.1f 秒后获取下一页",
                    self.config.request_interval_seconds,
                )
                self.sleeper(self.config.request_interval_seconds)
            page_size = min(
                self.config.page_size,
                self.config.candidate_limit - offset,
            )
            page_number += 1
            logger.info(
                "[Academic/ArXiv] 获取第 %d 页：start=%d，max_results=%d",
                page_number,
                offset,
                page_size,
            )
            response = self.client.get(
                "https://export.arxiv.org/api/query",
                params={
                    "search_query": query,
                    "start": offset,
                    "max_results": page_size,
                    "sortBy": "submittedDate",
                    "sortOrder": "descending",
                },
            )
            response.raise_for_status()
            page = parse_feed(response.text)
            papers.extend(page)
            logger.info("[Academic/ArXiv] 第 %d 页返回 %d 篇", page_number, len(page))
            if len(page) < page_size:
                break
            offset += len(page)

        unique = list({paper.source_id: paper for paper in papers}.values())
        filtered = [
            paper
            for paper in unique
            if paper.submitted_at and window.contains(paper.submitted_at)
        ]
        logger.info(
            "[Academic/ArXiv] 阶段 1/4 完成：分页返回 %d 篇，去重后 %d 篇，时间窗口内 %d 篇",
            len(papers),
            len(unique),
            len(filtered),
        )
        return filtered

    def enrich_introduction(self, paper: AcademicPaper) -> None:
        url = f"https://arxiv.org/html/{paper.source_id}"
        logger.info("[Academic/HTML] 开始提取 Introduction：%s (%s)", paper.source_id, url)
        try:
            response = self.client.get(url)
            if response.status_code == 404:
                logger.info(
                    "[Academic/HTML] %s 没有 HTML 版本，后续仅使用标题和摘要",
                    paper.source_id,
                )
                return
            response.raise_for_status()
            extracted = extract_introduction(response.text)
            paper.introduction = extracted[: self.config.introduction_max_chars]
            if paper.introduction:
                logger.info(
                    "[Academic/HTML] %s Introduction 提取成功：原始 %d 字符，送入 LLM %d 字符",
                    paper.source_id,
                    len(extracted),
                    len(paper.introduction),
                )
            else:
                logger.info(
                    "[Academic/HTML] %s HTML 中未识别到 Introduction，后续仅使用标题和摘要",
                    paper.source_id,
                )
        except httpx.HTTPError as exc:
            logger.warning("读取 ArXiv %s Introduction 失败: %s", paper.source_id, exc)


def build_query(profile: ProfileConfig, window: SearchWindow) -> str:
    interests = " OR ".join(f'all:"{_query_term(value)}"' for value in profile.interests if value)
    exclusions = " ".join(
        f'ANDNOT all:"{_query_term(value)}"' for value in profile.exclude_keywords if value
    )
    # The arXiv API date range syntax uses minute precision: YYYYMMDDHHMM.
    start = window.start_utc.strftime("%Y%m%d%H%M")
    end = window.end_utc.strftime("%Y%m%d%H%M")
    # Keep the date clause before ANDNOT. The arXiv query parser can otherwise
    # apply the date only to the final exclusion expression and return unbounded
    # recent matches for the OR group.
    return f"({interests}) AND submittedDate:[{start} TO {end}] {exclusions}".strip()


def _query_term(value: str) -> str:
    return value.replace("\\", " ").replace('"', " ").strip()


def parse_feed(content: str) -> list[AcademicPaper]:
    root = ET.fromstring(content)
    papers: list[AcademicPaper] = []
    for entry in root.findall(f"{ATOM}entry"):
        raw_id = _text(entry, "id")
        source_id = raw_id.rstrip("/").rsplit("/", 1)[-1]
        source_id = re.sub(r"v\d+$", "", source_id)
        submitted = _parse_datetime(_text(entry, "published"))
        url = next(
            (
                link.get("href", "")
                for link in entry.findall(f"{ATOM}link")
                if link.get("rel") == "alternate"
            ),
            f"https://arxiv.org/abs/{source_id}",
        )
        papers.append(
            AcademicPaper(
                source="arxiv",
                source_id=source_id,
                title=_clean(_text(entry, "title")),
                url=url,
                abstract=_clean(_text(entry, "summary")),
                authors=[
                    _clean(_text(author, "name"))
                    for author in entry.findall(f"{ATOM}author")
                ],
                submitted_at=submitted,
            )
        )
    return papers


def extract_introduction(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")
    heading = next(
        (
            node
            for node in soup.find_all(re.compile(r"^h[1-6]$"))
            if re.search(r"\bintroduction\b", node.get_text(" ", strip=True), re.IGNORECASE)
        ),
        None,
    )
    if heading is None:
        return ""
    level = int(heading.name[1])
    parts: list[str] = []
    for node in heading.find_all_next():
        if node is not heading and re.fullmatch(r"h[1-6]", node.name or ""):
            if int(node.name[1]) <= level:
                break
        if isinstance(node, Tag) and node.name == "p":
            text = _clean(node.get_text(" ", strip=True))
            if text and not any(text in existing for existing in parts):
                parts.append(text)
    return "\n\n".join(parts)


def _text(node: ET.Element, name: str) -> str:
    child = node.find(f"{ATOM}{name}")
    return child.text or "" if child is not None else ""


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
