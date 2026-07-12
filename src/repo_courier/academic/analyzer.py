from __future__ import annotations

import json
import logging
import re

import httpx
from json_repair import repair_json

from ..config import AcademicConfig, ProfileConfig, SummaryConfig
from ..models import AcademicPaper
from .prompts import PAPER_ANALYSIS_SYSTEM_PROMPT, paper_analysis_user_prompt

logger = logging.getLogger(__name__)


class PaperAnalyzer:
    def __init__(
        self,
        academic: AcademicConfig,
        summary: SummaryConfig,
        client: httpx.Client | None = None,
    ) -> None:
        self.academic = academic
        self.summary = summary
        self.client = client or httpx.Client(timeout=summary.timeout_seconds)

    def analyze(self, paper: AcademicPaper, profile: ProfileConfig) -> None:
        if not (
            self.academic.enabled
            and self.summary.enabled
            and self.academic.api_key
            and self.summary.model
        ):
            logger.info(
                "[Academic/LLM] %s 未满足调用条件，使用规则回退（enabled=%s, key=%s, model=%s）",
                paper.source_id,
                self.academic.enabled and self.summary.enabled,
                "已配置" if self.academic.api_key else "未配置",
                self.summary.model or "未配置",
            )
            self.fallback(paper)
            return
        try:
            logger.info(
                "[Academic/LLM] 开始分析 %s：intro=%d 字符，model=%s",
                paper.source_id,
                len(paper.introduction),
                self.summary.model,
            )
            response = self.client.post(
                f"{self.academic.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {self.academic.api_key}"},
                json={
                    "model": self.summary.model,
                    "temperature": 0.2,
                    "response_format": {"type": "json_object"},
                    "messages": [
                        {
                            "role": "system",
                            "content": PAPER_ANALYSIS_SYSTEM_PROMPT,
                        },
                        {
                            "role": "user",
                            "content": paper_analysis_user_prompt(paper, profile),
                        },
                    ],
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
            payload = json.loads(repair_json(cleaned))
            paper.relevance_score = _score(payload.get("relevance_score"))
            paper.innovation_score = _score(payload.get("innovation_score"))
            paper.summary = _truncate(str(payload.get("summary") or ""), 200)
            if not paper.summary:
                raise ValueError("论文总结为空")
            paper.analysis_status = "ai"
            logger.info(
                "[Academic/LLM] %s 分析完成：相关性=%d，创新性=%d，summary=%d 字符",
                paper.source_id,
                paper.relevance_score,
                paper.innovation_score,
                len(paper.summary),
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                "[Academic/LLM] %s 分析或 JSON 解析失败，使用规则回退：%s",
                paper.source_id,
                exc,
            )
            self.fallback(paper)

    @staticmethod
    def fallback(paper: AcademicPaper) -> None:
        paper.relevance_score = max(0, min(10, paper.rule_score))
        paper.innovation_score = 0
        paper.summary = _truncate(paper.abstract, 200) or _truncate(paper.title, 200)
        paper.analysis_status = "fallback"


def _score(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("评分必须是数字")
    score = int(value)
    if score != value or not 0 <= score <= 10:
        raise ValueError("评分超出 0 到 10")
    return score


def _truncate(value: str, limit: int) -> str:
    value = value.strip()
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"
