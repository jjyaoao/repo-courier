from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, SecretStr, field_validator

from .config import ReportConfig, load_config
from .runner import run

logger = logging.getLogger(__name__)

ASSET_DIR = Path(__file__).with_name("web_assets")
DEFAULT_AI_BASE_URL = "https://api.openai.com/v1"
SUPPORTED_LANGUAGES = {"", "python", "javascript", "typescript", "go", "rust", "java"}
MAX_REQUEST_BYTES = 16 * 1024


class PreviewRequest(BaseModel):
    interests: list[str] = Field(min_length=1, max_length=12)
    language: str = Field(default="", max_length=20)
    ai_base_url: str = Field(default=DEFAULT_AI_BASE_URL, max_length=300)
    ai_model: str = Field(default="", max_length=120)
    ai_api_key: SecretStr | None = Field(default=None, max_length=500)

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for raw_value in values:
            value = re.sub(r"\s+", " ", raw_value).strip()
            if not value:
                continue
            if len(value) > 40:
                raise ValueError("单个关注词不能超过 40 个字符")
            if value.lower() not in {item.lower() for item in cleaned}:
                cleaned.append(value)
        if not cleaned:
            raise ValueError("至少填写一个关注词")
        return cleaned

    @field_validator("language")
    @classmethod
    def supported_language(cls, value: str) -> str:
        normalized = value.strip().lower()
        if normalized not in SUPPORTED_LANGUAGES:
            raise ValueError("不支持该语言筛选")
        return normalized


def allowed_ai_base_urls() -> set[str]:
    configured = os.getenv("REPO_COURIER_ALLOWED_AI_BASE_URLS", "")
    values = {DEFAULT_AI_BASE_URL}
    values.update(item.strip().rstrip("/") for item in configured.split(",") if item.strip())
    return values


def validate_ai_settings(payload: PreviewRequest) -> tuple[str, str, str]:
    key = payload.ai_api_key.get_secret_value().strip() if payload.ai_api_key else ""
    model = payload.ai_model.strip()
    if bool(key) != bool(model):
        raise ValueError("启用 AI 时需要同时填写 API Key 和模型名称")
    if not key:
        return "", "", ""

    base_url = payload.ai_base_url.strip().rstrip("/")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("模型服务地址必须是不包含账号信息的 HTTPS 地址")
    if base_url not in allowed_ai_base_urls():
        raise ValueError("该模型服务地址未被当前站点允许")
    return base_url, model, key


def generate_preview(payload: PreviewRequest) -> dict[str, object]:
    base_url, model, api_key = validate_ai_settings(payload)
    config_path = os.getenv("REPO_COURIER_CONFIG", "config/config.yaml")
    config = load_config(config_path)
    config.profile.interests = payload.interests
    config.profile.daily_picks = 3
    config.github.language = payload.language
    config.summary.enabled = bool(api_key and model)
    config.summary.api_key = api_key
    config.summary.base_url = base_url or DEFAULT_AI_BASE_URL
    config.summary.model = model
    config.academic.enabled = False
    config.push.enabled = False

    with TemporaryDirectory(prefix="repo-courier-web-") as directory:
        config.report = ReportConfig(
            output_dir=str(Path(directory) / "reports"),
            data_dir=str(Path(directory) / "history"),
            title=config.report.title,
        )
        result = run(config, dry_run=True)

    repositories = [
        {
            "rank": item.pick_rank,
            "trending_rank": item.rank,
            "full_name": item.full_name,
            "url": item.url,
            "description": item.description,
            "summary": item.summary,
            "language": item.language,
            "stars": item.stars,
            "stars_today": item.stars_today,
            "forks": item.forks,
            "license": item.license,
            "relevance_score": item.relevance_score,
            "recommendation": item.recommendation,
            "why_for_you": item.why_for_you,
            "matched_interests": item.matched_interests,
            "highlights": item.highlights,
            "use_cases": item.use_cases,
            "risk_note": item.risk_note,
        }
        for item in result.repositories
    ]
    return {
        "scanned_count": result.scanned_count,
        "repositories": repositories,
        "used_ai": bool(api_key and model),
    }


def create_app() -> FastAPI:
    application = FastAPI(
        title="RepoCourier Web",
        description="从 GitHub Trending 中选出今天最值得打开的 3 个项目。",
        version="0.1.0-beta",
        docs_url=None,
        redoc_url=None,
    )
    application.state.preview_slots = asyncio.Semaphore(
        max(1, int(os.getenv("REPO_COURIER_WEB_CONCURRENCY", "2")))
    )
    application.mount("/assets", StaticFiles(directory=ASSET_DIR), name="assets")

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        try:
            content_length = int(request.headers.get("content-length", "0"))
        except ValueError:
            content_length = 0
        if content_length > MAX_REQUEST_BYTES:
            response = JSONResponse(status_code=413, content={"detail": "请求内容过大"})
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        )
        return response

    @application.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(ASSET_DIR / "index.html")

    @application.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/preview")
    async def preview(payload: PreviewRequest) -> dict[str, object]:
        try:
            async with application.state.preview_slots:
                return await run_in_threadpool(generate_preview, payload)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Web 预览生成失败")
            raise HTTPException(
                status_code=502,
                detail="暂时无法生成预览，请稍后再试",
            ) from exc

    return application


app = create_app()


def main() -> None:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - only possible without the web extra.
        raise RuntimeError("请先安装 Web 依赖: pip install 'repo-courier[web]'") from exc
    uvicorn.run(
        "repo_courier.web:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        proxy_headers=True,
    )
