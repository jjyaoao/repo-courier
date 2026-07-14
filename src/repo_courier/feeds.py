from __future__ import annotations

import hashlib
import json
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Generic, TypeVar
from urllib.parse import urldefrag

import httpx
from bs4 import BeautifulSoup
from json_repair import repair_json

from .academic.analyzer import _contains_chinese, _message_content, _score, _truncate
from .academic.base import SearchWindow
from .config import (
    AcademicConfig,
    FeedSourceConfig,
    ProfileConfig,
    SummaryConfig,
    TechBlogConfig,
    TechNewsConfig,
)
from .matching import contains, interest_terms, normalize
from .models import TechBlogPost, TechNewsPost

logger = logging.getLogger(__name__)

ATOM = "{http://www.w3.org/2005/Atom}"
CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
DC = "{http://purl.org/dc/elements/1.1/}"
USER_AGENT = "RepoCourier/0.1 (official technology feed reader)"


@dataclass(slots=True)
class FeedEntry:
    entry_id: str
    title: str
    url: str
    summary: str
    content: str
    authors: list[str]
    tags: list[str]
    published_at: datetime | None


@dataclass(slots=True)
class TechBlogRun:
    posts: list[TechBlogPost]
    scanned_count: int
    errors: dict[str, str]


@dataclass(slots=True)
class TechNewsRun:
    posts: list[TechNewsPost]
    scanned_count: int
    errors: dict[str, str]


FeedPost = TechBlogPost | TechNewsPost
PostT = TypeVar("PostT", TechBlogPost, TechNewsPost)


class FeedAnalyzer:
    def __init__(
        self,
        academic: AcademicConfig,
        summary: SummaryConfig,
        client: httpx.Client | None = None,
    ) -> None:
        self.academic = academic
        self.summary = summary
        self.client = client or httpx.Client(
            timeout=summary.timeout_seconds,
            verify=academic.verify_ssl,
        )

    def analyze(self, post: FeedPost, profile: ProfileConfig) -> None:
        if not (self.academic.api_key and self.academic.model):
            self.fallback(post)
            return
        try:
            response = self.client.post(
                self.academic.base_url,
                headers={"Authorization": f"Bearer {self.academic.api_key}"},
                json={
                    "model": self.academic.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {"role": "system", "content": _system_prompt(post)},
                        {"role": "user", "content": _user_prompt(post, profile)},
                    ],
                },
            )
            response.raise_for_status()
            content = _message_content(response.json())
            if not isinstance(content, str):
                raise ValueError("LLM message.content 必须是字符串")
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
            payload = json.loads(repair_json(cleaned))
            if not isinstance(payload, dict):
                raise ValueError("LLM 返回 JSON 的顶层必须是对象")
            post.relevance_score = _score(payload.get("relevance_score"))
            if isinstance(post, TechBlogPost):
                post.technical_depth_score = _score(payload.get("technical_depth_score"))
            else:
                post.importance_score = _score(payload.get("importance_score"))
            generated_summary = str(payload.get("summary") or "").strip()
            reason = str(payload.get("recommendation_reason") or "").strip()
            if not generated_summary or not reason:
                raise ValueError("中文摘要或推荐理由为空")
            if not _contains_chinese(generated_summary) or not _contains_chinese(reason):
                raise ValueError("摘要和推荐理由必须使用中文")
            post.summary = _truncate(generated_summary, 200)
            post.recommendation_reason = _truncate(reason, 100)
            post.analysis_status = "ai"
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning("[Feed/LLM] %s 分析失败，使用规则回退：%s", post.source_id, exc)
            self.fallback(post)

    @staticmethod
    def fallback(post: FeedPost) -> None:
        post.analysis_status = "fallback"
        post.relevance_score = max(0, min(10, round(post.rule_score / 10)))
        matched = "、".join(post.matched_keywords[:3])
        post.recommendation_reason = f"命中关注词：{matched}。" if matched else "根据规则分入选。"
        if not post.summary:
            post.summary = _truncate(post.content_excerpt or post.title, 200)


class _FeedPipeline(Generic[PostT]):
    category_name = "feed"

    def __init__(
        self,
        config: TechBlogConfig | TechNewsConfig,
        academic: AcademicConfig,
        summary: SummaryConfig,
        *,
        client: httpx.Client | None = None,
        analyzer: FeedAnalyzer | None = None,
    ) -> None:
        self.config = config
        self.client = client or httpx.Client(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        self.analyzer = analyzer or FeedAnalyzer(academic, summary)

    def _make_post(self, source: FeedSourceConfig, entry: FeedEntry) -> PostT:
        raise NotImplementedError

    def _run(
        self, profile: ProfileConfig, window: SearchWindow
    ) -> tuple[list[PostT], int, dict[str, str]]:
        if not self.config.enabled:
            return [], 0, {}
        entries, errors = self._fetch_sources(window)
        posts: list[PostT] = []
        seen_urls: set[str] = set()
        for source, entry in entries:
            canonical_url = _canonical_url(entry.url)
            if not entry.title or not canonical_url or canonical_url in seen_urls:
                continue
            seen_urls.add(canonical_url)
            entry.url = canonical_url
            post = self._make_post(source, entry)
            if score_post(post, profile):
                posts.append(post)
        shortlist = sorted(
            posts,
            key=lambda item: (-item.rule_score, -_timestamp(item.published_at), item.title.lower()),
        )[: self.config.final_picks * 2]
        workers = max(1, min(self.config.max_analysis_workers, len(shortlist) or 1))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            list(executor.map(lambda item: self.analyzer.analyze(item, profile), shortlist))
        eligible: list[PostT] = []
        for post in shortlist:
            if post.analysis_status == "ai" and post.relevance_score <= 3:
                continue
            post.final_score = combined_score(post)
            eligible.append(post)
        picks = sorted(
            eligible,
            key=lambda item: (
                -item.final_score,
                -_timestamp(item.published_at),
                item.title.lower(),
            ),
        )[: self.config.final_picks]
        for rank, post in enumerate(picks, start=1):
            post.pick_rank = rank
        logger.info(
            "[%s] 扫描 %d 条，规则初筛 %d 条，最终入选 %d 条",
            self.category_name,
            len(entries),
            len(shortlist),
            len(picks),
        )
        return picks, len(entries), errors

    def _fetch_sources(
        self, window: SearchWindow
    ) -> tuple[list[tuple[FeedSourceConfig, FeedEntry]], dict[str, str]]:
        collected: list[tuple[FeedSourceConfig, FeedEntry]] = []
        errors: dict[str, str] = {}

        def fetch(source: FeedSourceConfig) -> list[FeedEntry]:
            response = self.client.get(source.url)
            response.raise_for_status()
            return [
                entry
                for entry in parse_feed(response.text, self.config.content_max_chars)
                if entry.published_at and window.contains(entry.published_at)
            ]

        workers = max(1, min(len(self.config.sources) or 1, 10))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(fetch, source): source for source in self.config.sources}
            for future in as_completed(futures):
                source = futures[future]
                try:
                    collected.extend((source, entry) for entry in future.result())
                except (httpx.HTTPError, ET.ParseError, ValueError) as exc:
                    errors[source.source_id] = str(exc)
                    logger.warning("[%s/%s] RSS 获取失败：%s", self.category_name, source.name, exc)
        return collected, errors


class TechBlogPipeline(_FeedPipeline[TechBlogPost]):
    category_name = "TechBlog"

    def _make_post(self, source: FeedSourceConfig, entry: FeedEntry) -> TechBlogPost:
        return TechBlogPost(
            source_id=_post_id(source, entry),
            source_name=source.name,
            title=entry.title,
            url=entry.url,
            summary=entry.summary,
            content_excerpt=entry.content,
            authors=entry.authors,
            tags=entry.tags,
            published_at=entry.published_at,
        )

    def run(self, profile: ProfileConfig, window: SearchWindow) -> TechBlogRun:
        posts, scanned_count, errors = self._run(profile, window)
        return TechBlogRun(posts, scanned_count, errors)


class TechNewsPipeline(_FeedPipeline[TechNewsPost]):
    category_name = "TechNews"

    def _make_post(self, source: FeedSourceConfig, entry: FeedEntry) -> TechNewsPost:
        return TechNewsPost(
            source_id=_post_id(source, entry),
            source_name=source.name,
            title=entry.title,
            url=entry.url,
            summary=entry.summary,
            content_excerpt=entry.content,
            authors=entry.authors,
            tags=entry.tags,
            published_at=entry.published_at,
        )

    def run(self, profile: ProfileConfig, window: SearchWindow) -> TechNewsRun:
        posts, scanned_count, errors = self._run(profile, window)
        return TechNewsRun(posts, scanned_count, errors)


def score_post(post: FeedPost, profile: ProfileConfig) -> bool:
    title = normalize(post.title)
    tags = normalize(" ".join(post.tags))
    body = normalize(" ".join([post.summary, post.content_excerpt]))
    all_text = " ".join([title, tags, body])
    post.excluded_keywords = [
        keyword
        for keyword in profile.exclude_keywords
        if contains(all_text, normalize(keyword))
    ]
    if post.excluded_keywords:
        return False
    score = 0
    matched: list[str] = []
    for interest in profile.interests:
        terms = interest_terms(interest)
        if any(contains(title, term) for term in terms):
            score += 30
        elif any(contains(tags, term) for term in terms):
            score += 20
        elif any(contains(body, term) for term in terms):
            score += 10
        else:
            continue
        matched.append(interest)
    post.matched_keywords = list(dict.fromkeys(matched))
    post.rule_score = min(100, score)
    return bool(post.matched_keywords)


def combined_score(post: FeedPost) -> float:
    if post.analysis_status != "ai":
        return float(post.rule_score)
    secondary = (
        post.technical_depth_score if isinstance(post, TechBlogPost) else post.importance_score
    )
    llm_score = (post.relevance_score * 0.6 + secondary * 0.4) * 10
    return round(post.rule_score * 0.4 + llm_score * 0.6, 2)


def parse_feed(content: str, content_max_chars: int = 6000) -> list[FeedEntry]:
    root = ET.fromstring(content)
    if root.tag == f"{ATOM}feed" or root.findall(f"{ATOM}entry"):
        return [_parse_atom_entry(node, content_max_chars) for node in root.findall(f"{ATOM}entry")]
    return [_parse_rss_item(node, content_max_chars) for node in root.findall(".//item")]


def _parse_rss_item(node: ET.Element, limit: int) -> FeedEntry:
    summary_html = _text(node, "description")
    content_html = _text(node, f"{CONTENT}encoded")
    summary = _clean_html(summary_html)
    content = _content_excerpt(summary_html, content_html, limit)
    url = _text(node, "link")
    entry_id = _text(node, "guid") or url
    authors = _unique([_text(node, "author"), _text(node, f"{DC}creator")])
    tags = _unique([_clean_html(item.text or "") for item in node.findall("category")])
    published = _text(node, "pubDate") or _text(node, f"{DC}date")
    return FeedEntry(
        entry_id=entry_id,
        title=_clean_html(_text(node, "title")),
        url=url,
        summary=_truncate(summary, 500),
        content=content,
        authors=authors,
        tags=tags,
        published_at=_parse_datetime(published),
    )


def _parse_atom_entry(node: ET.Element, limit: int) -> FeedEntry:
    url = next(
        (
            link.get("href", "")
            for link in node.findall(f"{ATOM}link")
            if link.get("rel", "alternate") == "alternate"
        ),
        "",
    )
    summary_html = _text(node, f"{ATOM}summary")
    content_html = _text(node, f"{ATOM}content")
    authors = _unique(
        [_text(author, f"{ATOM}name") for author in node.findall(f"{ATOM}author")]
    )
    tags = _unique(
        [category.get("term", "") for category in node.findall(f"{ATOM}category")]
    )
    published = _text(node, f"{ATOM}published") or _text(node, f"{ATOM}updated")
    return FeedEntry(
        entry_id=_text(node, f"{ATOM}id") or url,
        title=_clean_html(_text(node, f"{ATOM}title")),
        url=url,
        summary=_truncate(_clean_html(summary_html), 500),
        content=_content_excerpt(summary_html, content_html, limit),
        authors=authors,
        tags=tags,
        published_at=_parse_datetime(published),
    )


def _system_prompt(post: FeedPost) -> str:
    if isinstance(post, TechBlogPost):
        secondary = (
            '"technical_depth_score": 0到10的整数，衡量架构、实现、算法、性能或工程经验深度'
        )
    else:
        secondary = '"importance_score": 0到10的整数，衡量产品、模型、平台或安全发布的重要性'
    return (
        "你是严谨的科技内容筛选助手，只能根据输入内容判断，不得臆造。"
        "只返回合法 JSON 对象。"
        '"relevance_score" 为0到10的整数，衡量与用户关键词的实际相关性；'
        f"{secondary}；"
        '"summary" 为不超过200字的中文摘要；'
        '"recommendation_reason" 为不超过100字的中文推荐理由。'
    )


def _user_prompt(post: FeedPost, profile: ProfileConfig) -> str:
    return json.dumps(
        {
            "category": "tech_blog" if isinstance(post, TechBlogPost) else "tech_news",
            "profile_keywords": profile.interests,
            "source": post.source_name,
            "title": post.title,
            "tags": post.tags,
            "published_at": post.published_at.isoformat() if post.published_at else None,
            "content": post.content_excerpt,
            "matched_keywords": post.matched_keywords,
            "rule_score": post.rule_score,
        },
        ensure_ascii=False,
    )


def _content_excerpt(summary_html: str, content_html: str, limit: int) -> str:
    parts = _unique([_clean_html(summary_html), _clean_html(content_html)])
    return _truncate("\n\n".join(parts), limit)


def _clean_html(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ")).strip()


def _parse_datetime(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _text(node: ET.Element, name: str) -> str:
    child = node.find(name)
    return (child.text or "").strip() if child is not None else ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _canonical_url(url: str) -> str:
    return urldefrag(url.strip())[0].rstrip("/")


def _post_id(source: FeedSourceConfig, entry: FeedEntry) -> str:
    raw = entry.entry_id or entry.url
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"{source.source_id}:{digest}"


def _timestamp(value: datetime | None) -> float:
    return value.timestamp() if value else 0.0
