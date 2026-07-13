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
        self.client = client or httpx.Client(
            timeout=summary.timeout_seconds,
            verify=academic.verify_ssl,
        )
        if client is None and not academic.verify_ssl:
            logger.warning("[Academic/LLM] SSL 证书校验已关闭，仅建议用于受信任的测试环境")

    def analyze(self, paper: AcademicPaper, profile: ProfileConfig) -> None:
        if not (
            self.academic.enabled
            and self.summary.enabled
            and self.academic.api_key
            and self.academic.model
        ):
            logger.info(
                "[Academic/LLM] %s 未满足调用条件，使用规则回退（enabled=%s, key=%s, model=%s）",
                paper.source_id,
                self.academic.enabled and self.summary.enabled,
                "已配置" if self.academic.api_key else "未配置",
                self.academic.model or "未配置",
            )
            self.fallback(paper)
            return
        try:
            logger.info(
                "[Academic/LLM] 开始分析 %s：intro=%d 字符，model=%s",
                paper.source_id,
                len(paper.introduction),
                self.academic.model,
            )
            response = self.client.post(
                self.academic.base_url,
                headers={"Authorization": f"Bearer {self.academic.api_key}"},
                json={
                    "model": self.academic.model,
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
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError:
                logger.warning(
                    "[Academic/LLM] %s HTTP %d 原始响应：%s",
                    paper.source_id,
                    response.status_code,
                    response.text,
                )
                raise
            response_payload = response.json()
            logger.info(
                "[Academic/LLM] %s HTTP %s 响应体：%s",
                paper.source_id,
                getattr(response, "status_code", "未知"),
                _response_body(response, response_payload),
            )
            content = _message_content(response_payload)
            if not isinstance(content, str):
                raise ValueError("LLM message.content 必须是字符串")
            logger.info(
                "[Academic/LLM] %s 模型输出：%s",
                paper.source_id,
                content,
            )
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
            payload = json.loads(repair_json(cleaned))
            if not isinstance(payload, dict):
                raise ValueError("LLM 返回 JSON 的顶层必须是对象")
            paper.relevance_score = _score(payload.get("relevance_score"))
            paper.innovation_score = _score(payload.get("innovation_score"))
            motivation = str(payload.get("research_motivation") or "").strip()
            contributions = str(payload.get("core_contributions") or "").strip()
            if not motivation or not contributions:
                raise ValueError("研究动机或核心贡献为空")
            if not _contains_chinese(motivation) or not _contains_chinese(contributions):
                raise ValueError("研究动机和核心贡献必须使用中文")
            paper.research_motivation = _truncate(motivation, 200)
            paper.core_contributions = _truncate(contributions, 200)
            paper.analysis_status = "ai"
            logger.info(
                "[Academic/LLM] %s 分析完成：相关性=%d，创新性=%d，中文分析=%d 字符",
                paper.source_id,
                paper.relevance_score,
                paper.innovation_score,
                len(paper.research_motivation) + len(paper.core_contributions),
            )
        except (
            httpx.HTTPError,
            KeyError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            if isinstance(exc, httpx.TransportError):
                logger.warning(
                    "[Academic/LLM] %s 请求未收到 HTTP 响应：%s",
                    paper.source_id,
                    exc,
                )
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
        paper.research_motivation = "LLM 分析失败，未能可靠提取研究动机。"
        source = paper.abstract or paper.title
        paper.core_contributions = _truncate(f"原始论文内容：{source}", 200)
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


def _contains_chinese(value: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", value))


def _response_body(response: object, payload: object) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str):
        return text
    return json.dumps(payload, ensure_ascii=False)


def _message_content(payload: object) -> object:
    if not isinstance(payload, dict):
        raise ValueError(f"LLM HTTP 响应的顶层必须是对象，实际为 {type(payload).__name__}")
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        fields = ", ".join(str(key) for key in payload) or "<empty>"
        raise ValueError(f"LLM HTTP 响应缺少非空 choices，顶层字段：{fields}")
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("LLM choices[0] 必须是对象")
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("LLM choices[0].message 必须是对象")
    if "content" not in message:
        raise ValueError("LLM choices[0].message 缺少 content")
    return message["content"]
