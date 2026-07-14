from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class GitHubConfig:
    token: str = ""
    language: str = ""
    spoken_language_code: str = ""
    since: str = "daily"
    limit: int = 10
    include_readme: bool = True
    readme_max_chars: int = 6000


@dataclass(slots=True)
class SummaryConfig:
    enabled: bool = True
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = ""
    language: str = "zh-CN"
    timeout_seconds: float = 90.0


@dataclass(slots=True)
class ProfileConfig:
    interests: list[str] = field(
        default_factory=lambda: ["agent", "llm", "mcp", "developer tools", "automation"]
    )
    exclude_keywords: list[str] = field(
        default_factory=lambda: ["awesome list", "interview", "tutorial collection"]
    )
    daily_picks: int = 3


@dataclass(slots=True)
class ArxivConfig:
    enabled: bool = True
    candidate_limit: int = 500
    page_size: int = 100
    request_interval_seconds: float = 3.0
    final_picks: int = 3
    introduction_max_chars: int = 12000
    max_analysis_workers: int = 50


@dataclass(slots=True)
class AcademicConfig:
    enabled: bool = False
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1/chat/completions"
    model: str = ""
    verify_ssl: bool = True
    arxiv: ArxivConfig = field(default_factory=ArxivConfig)


@dataclass(slots=True)
class ReportConfig:
    output_dir: str = "reports"
    data_dir: str = "data/history"
    title: str = "RepoCourier · GitHub Trending 日报"


@dataclass(slots=True)
class PushConfig:
    enabled: bool = True
    feishu_webhook: str = ""
    wecom_webhook: str = ""
    serverchan_sendkey: str = ""
    onebot_url: str = ""
    onebot_token: str = ""
    onebot_user_id: str = ""


@dataclass(slots=True)
class AppConfig:
    github: GitHubConfig = field(default_factory=GitHubConfig)
    summary: SummaryConfig = field(default_factory=SummaryConfig)
    profile: ProfileConfig = field(default_factory=ProfileConfig)
    academic: AcademicConfig = field(default_factory=AcademicConfig)
    report: ReportConfig = field(default_factory=ReportConfig)
    push: PushConfig = field(default_factory=PushConfig)


def _section(data: dict[str, Any], name: str) -> dict[str, Any]:
    value = data.get(name, {})
    return value if isinstance(value, dict) else {}


def load_config(path: str | Path = "config/config.yaml") -> AppConfig:
    config_path = Path(path)
    data: dict[str, Any] = {}
    if config_path.exists():
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ValueError(f"配置文件根节点必须是对象: {config_path}")
        data = loaded

    github = GitHubConfig(**_known(GitHubConfig, _section(data, "github")))
    summary_values = _known(SummaryConfig, _section(data, "summary"))
    summary_values.pop("api_key", None)
    summary = SummaryConfig(**summary_values)
    profile = ProfileConfig(**_known(ProfileConfig, _section(data, "profile")))
    academic_data = _section(data, "academic")
    sources_data = _section(academic_data, "sources")
    arxiv_values = _known(ArxivConfig, _section(sources_data, "arxiv"))
    for name in (
        "candidate_limit",
        "page_size",
        "final_picks",
        "introduction_max_chars",
        "max_analysis_workers",
    ):
        if name in arxiv_values:
            arxiv_values[name] = _positive_int(arxiv_values[name], f"academic.sources.arxiv.{name}")
    if "request_interval_seconds" in arxiv_values:
        arxiv_values["request_interval_seconds"] = _non_negative_float(
            arxiv_values["request_interval_seconds"],
            "academic.sources.arxiv.request_interval_seconds",
        )
    arxiv = ArxivConfig(**arxiv_values)
    academic_values = _known(AcademicConfig, academic_data)
    academic_values.pop("api_key", None)
    academic_values.pop("arxiv", None)
    academic = AcademicConfig(**academic_values, arxiv=arxiv)
    report = ReportConfig(**_known(ReportConfig, _section(data, "report")))
    push = PushConfig(**_known(PushConfig, _section(data, "push")))

    github.token = _env("GITHUB_TOKEN", github.token)
    summary.api_key = os.getenv("AI_API_KEY", "")
    summary.base_url = _env("AI_BASE_URL", summary.base_url)
    summary.model = _env("AI_MODEL", summary.model)
    academic.api_key = os.getenv(
        "ACADEMIC_API_KEY",
        os.getenv("academic_api_key", ""),  # Backward compatibility with pre-0.1 configs.
    )
    push.feishu_webhook = _env("FEISHU_WEBHOOK", push.feishu_webhook)
    push.wecom_webhook = _env("WECOM_WEBHOOK", push.wecom_webhook)
    push.serverchan_sendkey = _env("SERVERCHAN_SENDKEY", push.serverchan_sendkey)
    push.onebot_url = _env("ONEBOT_URL", push.onebot_url)
    push.onebot_token = _env("ONEBOT_TOKEN", push.onebot_token)
    push.onebot_user_id = _env("ONEBOT_USER_ID", push.onebot_user_id)
    interests = os.getenv("REPO_COURIER_INTERESTS", "")
    if interests:
        profile.interests = [item.strip() for item in interests.split(",") if item.strip()]
    return AppConfig(
        github=github,
        summary=summary,
        profile=profile,
        academic=academic,
        report=report,
        push=push,
    )


def _known(cls: type[Any], values: dict[str, Any]) -> dict[str, Any]:
    fields = cls.__dataclass_fields__.keys()
    return {key: value for key, value in values.items() if key in fields}


def _env(name: str, default: str) -> str:
    return os.getenv(name) or default


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"配置 {name} 必须是正整数，当前值: {value!r}")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"配置 {name} 必须是正整数，不能使用表达式，当前值: {value!r}"
        ) from exc
    if parsed <= 0 or str(parsed) != str(value).strip():
        raise ValueError(f"配置 {name} 必须是正整数，当前值: {value!r}")
    return parsed


def _non_negative_float(value: object, name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"配置 {name} 必须是非负数，当前值: {value!r}")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"配置 {name} 必须是非负数，当前值: {value!r}") from exc
    if parsed < 0:
        raise ValueError(f"配置 {name} 必须是非负数，当前值: {value!r}")
    return parsed
