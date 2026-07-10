from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor

import httpx

from .config import GitHubConfig
from .models import Repository
from .trending import USER_AGENT

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self, config: GitHubConfig, client: httpx.Client | None = None) -> None:
        self.config = config
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        }
        if config.token:
            headers["Authorization"] = f"Bearer {config.token}"
        self.client = client or httpx.Client(
            base_url="https://api.github.com", timeout=30, headers=headers
        )

    def enrich(self, repositories: list[Repository]) -> list[Repository]:
        # httpx.Client can be shared between threads. A small pool keeps the CLI quick
        # without creating an aggressive burst against the public GitHub API.
        with ThreadPoolExecutor(max_workers=min(5, len(repositories) or 1)) as executor:
            list(executor.map(self._enrich_one, repositories))
        return repositories

    def _enrich_one(self, repository: Repository) -> None:
        try:
            response = self.client.get(f"/repos/{repository.full_name}")
            response.raise_for_status()
            data = response.json()
            repository.description = data.get("description") or repository.description
            repository.language = data.get("language") or repository.language
            repository.stars = int(data.get("stargazers_count") or repository.stars)
            repository.forks = int(data.get("forks_count") or repository.forks)
            repository.topics = list(data.get("topics") or [])
            repository.license = (data.get("license") or {}).get("spdx_id") or ""
            repository.homepage = data.get("homepage") or ""
            repository.open_issues = int(data.get("open_issues_count") or 0)
            repository.updated_at = data.get("updated_at") or ""
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            logger.warning("补充 %s 信息失败，保留 Trending 数据: %s", repository.full_name, exc)

    def enrich_readmes(self, repositories: list[Repository]) -> None:
        if not self.config.include_readme or not repositories:
            return
        with ThreadPoolExecutor(max_workers=min(3, len(repositories))) as executor:
            list(executor.map(self._enrich_readme, repositories))

    def _enrich_readme(self, repository: Repository) -> None:
        try:
            repository.readme_excerpt = self._readme(repository)
        except httpx.HTTPError as exc:
            logger.warning("读取 %s README 失败，继续生成报告: %s", repository.full_name, exc)

    def _readme(self, repository: Repository) -> str:
        response = self.client.get(
            f"/repos/{repository.full_name}/readme",
            headers={"Accept": "application/vnd.github.raw+json"},
        )
        if response.status_code == 404:
            return ""
        response.raise_for_status()
        return response.text[: self.config.readme_max_chars]
