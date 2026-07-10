import json
from datetime import date

from repo_courier.config import ReportConfig
from repo_courier.models import Repository
from repo_courier.report import ReportWriter


def _repository() -> Repository:
    return Repository(
        rank=1,
        owner="acme",
        name="rocket",
        url="https://github.com/acme/rocket",
        description="Ship applications",
        language="Python",
        stars=1_000,
        stars_today=100,
        license="MIT",
        summary="一个快速的应用交付工具。",
        highlights=["上手简单", "自动化能力强"],
        use_cases=["持续交付"],
        category="开发工具",
        relevance_score=82,
        recommendation="深挖",
        why_for_you="命中你的关注词：developer tools。",
        matched_interests=["developer tools"],
        pick_rank=1,
    )


def test_writer_outputs_three_formats(tmp_path) -> None:
    writer = ReportWriter(
        ReportConfig(output_dir=str(tmp_path / "reports"), data_dir=str(tmp_path / "history"))
    )
    paths = writer.write([_repository()], date(2026, 7, 10))

    assert set(paths) == {"markdown", "html", "json"}
    assert "acme/rocket" in paths["markdown"].read_text(encoding="utf-8")
    assert "为什么适合你" in paths["markdown"].read_text(encoding="utf-8")
    assert "<!doctype html>" in paths["html"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["repositories"][0]["full_name"] == "acme/rocket"


def test_digest_is_short_and_contains_links() -> None:
    digest = ReportWriter(ReportConfig()).digest([_repository()], date(2026, 7, 10))
    assert "acme/rocket" in digest
    assert "https://github.com/acme/rocket" in digest
