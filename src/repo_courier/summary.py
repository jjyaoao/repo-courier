from __future__ import annotations

import json
import logging
import re

import httpx

from .config import SummaryConfig
from .models import Repository

logger = logging.getLogger(__name__)


class Summarizer:
    def __init__(self, config: SummaryConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        self.client = client or httpx.Client(timeout=config.timeout_seconds)

    def summarize(self, repositories: list[Repository]) -> list[Repository]:
        if self.config.enabled and self.config.api_key and self.config.model:
            try:
                self._ai_summarize(repositories)
                return repositories
            except (httpx.HTTPError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                logger.warning("AI 摘要失败，将使用本地规则摘要: %s", exc)
        for repository in repositories:
            self._fallback(repository)
        return repositories

    def _ai_summarize(self, repositories: list[Repository]) -> None:
        inputs = [
            {
                "full_name": item.full_name,
                "description": item.description,
                "language": item.language,
                "topics": item.topics,
                "stars": item.stars,
                "stars_today": item.stars_today,
                "license": item.license,
                "readme_excerpt": item.readme_excerpt,
            }
            for item in repositories
        ]
        system = (
            "你是资深开源项目分析师。根据给定事实做简洁、克制的中文分析，不得臆造。"
            "只返回 JSON 数组。每项字段必须为 full_name, summary, highlights, use_cases, "
            "category, risk_note；highlights 和 use_cases 是各 1-3 条的字符串数组。"
        )
        response = self.client.post(
            f"{self.config.base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {self.config.api_key}"},
            json={
                "model": self.config.model,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": "分析以下项目。返回对象格式 {\"repositories\": [...]}：\n"
                        + json.dumps(inputs, ensure_ascii=False),
                    },
                ],
            },
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = self._parse_json(content)
        items = payload.get("repositories", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise ValueError("AI 返回内容不是项目数组")
        results = {item.get("full_name"): item for item in items if isinstance(item, dict)}
        for repository in repositories:
            item = results.get(repository.full_name)
            if not item:
                self._fallback(repository)
                continue
            repository.summary = str(item.get("summary") or repository.description)
            repository.highlights = _strings(item.get("highlights"))
            repository.use_cases = _strings(item.get("use_cases"))
            repository.category = str(item.get("category") or "其他")
            repository.risk_note = str(item.get("risk_note") or "")

    @staticmethod
    def _parse_json(content: str) -> object:
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip())
        return json.loads(cleaned)

    @staticmethod
    def _fallback(repository: Repository) -> None:
        topic_text = "、".join(repository.topics[:4])
        description = repository.description.strip().rstrip("。.")
        repository.summary = description or f"一个以 {repository.language} 为主的开源项目"
        repository.highlights = [
            f"今日新增约 {repository.stars_today:,} Stars",
            f"主要语言：{repository.language}",
        ]
        if topic_text:
            repository.highlights.append(f"关键词：{topic_text}")
        repository.use_cases = _infer_use_cases(repository)
        repository.category = _infer_category(repository)
        if not repository.license:
            repository.risk_note = "未从 GitHub 元数据识别到开源许可证，采用前请确认授权。"


def _strings(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()][:3]


def _infer_category(repository: Repository) -> str:
    text = " ".join(
        [repository.name, repository.description, repository.language, *repository.topics]
    ).lower()
    categories = [
        ("AI / 机器学习", ("ai", "llm", "machine-learning", "agent", "model")),
        ("开发工具", ("developer", "cli", "tool", "sdk", "ide", "terminal")),
        ("Web / 应用", ("web", "frontend", "backend", "react", "vue", "app")),
        ("数据 / 基础设施", ("database", "data", "cloud", "kubernetes", "infra")),
        ("安全", ("security", "privacy", "vulnerability", "pentest")),
        ("学习资源", ("tutorial", "awesome", "learn", "course", "book")),
    ]
    for category, keywords in categories:
        if any(keyword in text for keyword in keywords):
            return category
    return "其他"


def _infer_use_cases(repository: Repository) -> list[str]:
    category = _infer_category(repository)
    mapping = {
        "AI / 机器学习": ["AI 原型验证与能力集成"],
        "开发工具": ["提升开发、调试或自动化效率"],
        "Web / 应用": ["Web 产品开发与技术选型参考"],
        "数据 / 基础设施": ["数据处理或基础设施建设"],
        "安全": ["安全研究与防护能力建设"],
        "学习资源": ["系统学习与团队知识库建设"],
        "其他": ["技术调研与开源方案选型"],
    }
    return mapping[category]
