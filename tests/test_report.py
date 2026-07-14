import json
from datetime import date

from repo_courier.config import ReportConfig
from repo_courier.models import (
    AcademicPaper,
    DailyReport,
    Repository,
    TechBlogPost,
    TechNewsPost,
)
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
    paths = writer.write(DailyReport(repositories=[_repository()]), date(2026, 7, 10))

    assert set(paths) == {"markdown", "html", "json"}
    assert "acme/rocket" in paths["markdown"].read_text(encoding="utf-8")
    assert "为什么适合你" in paths["markdown"].read_text(encoding="utf-8")
    assert "<!doctype html>" in paths["html"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["repositories"][0]["full_name"] == "acme/rocket"


def test_digest_is_short_and_contains_links() -> None:
    digest = ReportWriter(ReportConfig()).digest(
        DailyReport(repositories=[_repository()]), date(2026, 7, 10)
    )
    assert "acme/rocket" in digest
    assert "https://github.com/acme/rocket" in digest


def test_writer_merges_academic_only_at_report_layer(tmp_path) -> None:
    paper = AcademicPaper(
        source="arxiv",
        source_id="2607.00001",
        title="Agent Research",
        url="https://arxiv.org/abs/2607.00001",
        relevance_score=9,
        innovation_score=8,
        combined_score=12.8,
        research_motivation="现有方法难以稳定完成复杂任务。",
        core_contributions="提出新的智能体协作方法。",
        pick_rank=1,
    )
    writer = ReportWriter(ReportConfig(output_dir=str(tmp_path / "reports")))

    paths = writer.write(
        DailyReport(repositories=[_repository()], papers=[paper]),
        date(2026, 7, 12),
    )

    markdown = paths["markdown"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert "## GitHub 推荐" in markdown
    assert "## 学术论文" in markdown
    assert "研究动机" in markdown
    assert "核心贡献" in markdown
    assert payload["repositories"][0]["full_name"] == "acme/rocket"
    assert payload["academic"]["papers"][0]["source_id"] == "2607.00001"


def test_writer_keeps_technology_blog_and_news_as_separate_sections(tmp_path) -> None:
    blog = TechBlogPost(
        source_id="cloudflare:1",
        source_name="Cloudflare Blog",
        title="Agent infrastructure",
        url="https://example.com/blog",
        summary="技术博客摘要",
        matched_keywords=["agent"],
        relevance_score=8,
        technical_depth_score=7,
        final_score=69.6,
        recommendation_reason="包含具体工程实现。",
        pick_rank=1,
    )
    news = TechNewsPost(
        source_id="apple:1",
        source_name="Apple Newsroom",
        title="AI product launch",
        url="https://example.com/news",
        summary="科技新闻摘要",
        matched_keywords=["agent"],
        relevance_score=8,
        importance_score=9,
        final_score=74.4,
        recommendation_reason="属于重要产品发布。",
        pick_rank=1,
    )
    writer = ReportWriter(ReportConfig(output_dir=str(tmp_path / "reports")))

    paths = writer.write(
        DailyReport(tech_blogs=[blog], tech_news=[news]), date(2026, 7, 12)
    )

    markdown = paths["markdown"].read_text(encoding="utf-8")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert "## 科技技术博客" in markdown
    assert "## 科技新闻发布" in markdown
    assert payload["tech_blogs"]["posts"][0]["source_id"] == "cloudflare:1"
    assert payload["tech_news"]["posts"][0]["source_id"] == "apple:1"
