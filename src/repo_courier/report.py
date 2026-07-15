# ruff: noqa: E501
from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

from .academic.base import BEIJING
from .config import ReportConfig
from .models import AcademicPaper, DailyReport, TechBlogPost, TechNewsPost


class ReportWriter:
    def __init__(self, config: ReportConfig) -> None:
        self.config = config

    def write(self, report: DailyReport, day: date) -> dict[str, Path]:
        output_dir = Path(self.config.output_dir) / day.isoformat()
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "markdown": output_dir / "daily.md",
            "html": output_dir / "daily.html",
            "json": output_dir / "daily.json",
        }
        paths["markdown"].write_text(self.markdown(report, day), encoding="utf-8")
        paths["html"].write_text(self.html(report, day), encoding="utf-8")
        paths["json"].write_text(
            json.dumps(
                {
                    "date": day.isoformat(),
                    "academic_window": report.academic_window,
                    "repositories": [item.to_dict() for item in report.repositories],
                    "academic": {
                        "papers": [item.to_dict() for item in report.papers],
                        "error": report.academic_error or None,
                    },
                    "tech_blogs": {
                        "posts": [item.to_dict() for item in report.tech_blogs],
                        "errors": report.tech_blog_errors,
                    },
                    "tech_news": {
                        "posts": [item.to_dict() for item in report.tech_news],
                        "errors": report.tech_news_errors,
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return paths

    def markdown(self, report: DailyReport, day: date) -> str:
        repositories = report.repositories
        lines = [
            f"# {self.config.title}",
            "",
            f"> {day.isoformat()} · {len(repositories)} 个开源项目 · {len(report.papers)} 篇论文 · "
            f"{len(report.tech_blogs)} 篇技术博客 · {len(report.tech_news)} 条科技新闻",
            "",
            "根据你的关注词对 GitHub Trending 重新排序。分数表示与你的匹配程度，"
            "不是项目质量的绝对排名。",
            "",
            "## GitHub 推荐",
            "",
        ]
        for item in repositories:
            lines.extend(
                [
                    f"### {item.pick_rank}. [{item.full_name}]({item.url})",
                    "",
                    f"`{item.recommendation}` · 匹配度 **{item.relevance_score}/100** · "
                    f"Trending 第 {item.rank} 名 `{item.rank_change}`",
                    "",
                    f"> **为什么适合你**：{item.why_for_you}",
                    "",
                    item.summary or item.description,
                    "",
                    f"**数据**：⭐ {item.stars:,} · 今日 +{item.stars_today:,} · "
                    f"Fork {item.forks:,} · {item.language} · {item.license or '许可证未知'}",
                    "",
                    "**特点**",
                    "",
                    *[f"- {value}" for value in item.highlights],
                    "",
                    "**适合场景**",
                    "",
                    *[f"- {value}" for value in item.use_cases],
                    "",
                ]
            )
            if item.risk_note:
                lines.extend([f"> 注意：{item.risk_note}", ""])
        lines.extend(["## 学术论文", ""])
        if report.academic_error:
            lines.extend(["> Academic 数据源本次获取失败，GitHub 报告不受影响。", ""])
        elif not report.papers:
            lines.extend(["本检索窗口没有入选论文。", ""])
        for paper in report.papers:
            lines.extend(self._paper_markdown(paper))
        lines.extend(["## 科技技术博客", ""])
        lines.extend(self._feed_errors_markdown(report.tech_blog_errors))
        if not report.tech_blogs:
            lines.extend(["本检索窗口没有入选技术博客。", ""])
        for post in report.tech_blogs:
            lines.extend(self._blog_markdown(post))
        lines.extend(["## 科技新闻发布", ""])
        lines.extend(self._feed_errors_markdown(report.tech_news_errors))
        if not report.tech_news:
            lines.extend(["本检索窗口没有入选科技新闻。", ""])
        for post in report.tech_news:
            lines.extend(self._news_markdown(post))
        lines.extend(
            [
                "---",
                "",
                "由 [RepoCourier](https://github.com/jjyaoao/repo-courier) 自动生成。",
                "",
            ]
        )
        return "\n".join(lines)

    def html(self, report: DailyReport, day: date) -> str:
        repositories = report.repositories
        cards = []
        for item in repositories:
            highlights = "".join(f"<li>{html.escape(value)}</li>" for value in item.highlights)
            use_cases = "".join(f"<li>{html.escape(value)}</li>" for value in item.use_cases)
            risk = f'<p class="risk">⚠ {html.escape(item.risk_note)}</p>' if item.risk_note else ""
            cards.append(
                f"""<article><div class="rank">{item.pick_rank}</div><div class="content">
                <h2><a href="{html.escape(item.url)}">{html.escape(item.full_name)}</a>
                <small>{html.escape(item.recommendation)} · {item.relevance_score}/100</small></h2>
                <p class="why"><strong>为什么适合你：</strong>{html.escape(item.why_for_you)}</p>
                <p>{html.escape(item.summary or item.description)}</p>
                <div class="meta">Trending #{item.rank} · ⭐ {item.stars:,} · 今日 +{item.stars_today:,} ·
                Fork {item.forks:,} · {html.escape(item.language)} · {html.escape(item.category)}</div>
                <div class="columns"><section><h3>特点</h3><ul>{highlights}</ul></section>
                <section><h3>适合场景</h3><ul>{use_cases}</ul></section></div>{risk}</div></article>"""
            )
        paper_cards = "".join(self._paper_html(paper) for paper in report.papers)
        if report.academic_error:
            paper_cards = '<p class="risk">Academic 数据源本次获取失败，GitHub 报告不受影响。</p>'
        elif not paper_cards:
            paper_cards = "<p>本检索窗口没有入选论文。</p>"
        blog_cards = "".join(self._blog_html(post) for post in report.tech_blogs)
        news_cards = "".join(self._news_html(post) for post in report.tech_news)
        blog_cards = self._feed_section_html(
            blog_cards, report.tech_blog_errors, "本检索窗口没有入选技术博客。"
        )
        news_cards = self._feed_section_html(
            news_cards, report.tech_news_errors, "本检索窗口没有入选科技新闻。"
        )
        return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(self.config.title)}</title>
<style>body{{margin:0;background:#f6f8fa;color:#1f2328;font:15px/1.6 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:32px 18px}}header{{padding:26px;background:#0d1117;color:white;border-radius:16px;margin-bottom:18px}}header h1{{margin:0 0 6px}}article{{display:flex;gap:18px;background:white;padding:24px;margin:14px 0;border:1px solid #d0d7de;border-radius:14px}}.rank{{font-size:32px;font-weight:800;color:#8250df}}.content{{flex:1}}h2{{margin:0}}h2 a{{color:#0969da;text-decoration:none}}small{{font-size:12px;background:#fbefff;color:#8250df;padding:3px 7px;border-radius:12px}}.why{{background:#f6f8ff;border-left:4px solid #8250df;padding:10px 12px}}.meta{{color:#59636e;margin:12px 0}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}h3{{font-size:14px;margin-bottom:2px}}.risk{{background:#fff8c5;padding:8px 12px;border-radius:8px}}footer{{text-align:center;color:#656d76;padding:20px}}@media(max-width:600px){{.columns{{grid-template-columns:1fr}}article{{padding:16px}}}}</style></head>
<body><main><header><h1>{html.escape(self.config.title)}</h1><div>{day.isoformat()} · {len(repositories)} 个开源项目 · {len(report.papers)} 篇论文 · {len(report.tech_blogs)} 篇技术博客 · {len(report.tech_news)} 条科技新闻</div></header>
<h1>GitHub 推荐</h1>{''.join(cards)}<h1>学术论文</h1>{paper_cards}<h1>科技技术博客</h1>{blog_cards}<h1>科技新闻发布</h1>{news_cards}<footer>Generated by RepoCourier</footer></main></body></html>"""

    def digest(self, report: DailyReport, day: date, limit: int = 5) -> str:
        repositories = report.repositories
        lines = [f"📮 RepoCourier · {day.isoformat()}", f"今天只看这 {min(limit, len(repositories))} 个：", ""]
        for item in repositories[:limit]:
            lines.extend(
                [
                    f"{item.pick_rank}. [{item.recommendation} {item.relevance_score}/100] "
                    f"{item.full_name} · +{item.stars_today:,} ⭐",
                    f"为什么：{item.why_for_you}",
                    (item.summary or item.description)[:120],
                    item.url,
                    "",
                ]
            )
        if report.papers:
            lines.extend(["📚 学术论文", ""])
            for paper in report.papers:
                lines.extend(
                    [
                        f"{paper.pick_rank}. [相关 {paper.relevance_score}/10 · 创新 {paper.innovation_score}/10] {paper.title}",
                        f"研究动机：{paper.research_motivation[:120]}",
                        f"核心贡献：{paper.core_contributions[:120]}",
                        paper.url,
                        "",
                    ]
                )
        if report.tech_blogs:
            lines.extend(["🛠 科技技术博客", ""])
            for post in report.tech_blogs:
                lines.extend(self._feed_digest(post, "创新", post.innovation_score))
        if report.tech_news:
            lines.extend(["📰 科技新闻发布", ""])
            for post in report.tech_news:
                lines.extend(self._feed_digest(post, "创新", post.innovation_score))
        lines.append("少看榜单，多看真正与你有关的内容。")
        return "\n".join(lines)

    @staticmethod
    def _paper_markdown(paper: AcademicPaper) -> list[str]:
        authors = "、".join(paper.authors[:5]) or "作者未知"
        submitted = paper.submitted_at.date().isoformat() if paper.submitted_at else "未知"
        return [
            f"### {paper.pick_rank}. [{paper.title}]({paper.url})",
            "",
            f"匹配度 **{paper.relevance_score}/10** · 创新性 **{paper.innovation_score}/10** · 综合分 **{paper.combined_score:.1f}**",
            "",
            f"**研究动机**：{paper.research_motivation}",
            "",
            f"**核心贡献**：{paper.core_contributions}",
            "",
            f"**作者**：{authors} · **提交日期**：{submitted} · **来源**：ArXiv",
            "",
        ]

    @staticmethod
    def _paper_html(paper: AcademicPaper) -> str:
        authors = "、".join(paper.authors[:5]) or "作者未知"
        return f"""<article><div class="rank">{paper.pick_rank}</div><div class="content">
        <h2><a href="{html.escape(paper.url)}">{html.escape(paper.title)}</a>
        <small>相关 {paper.relevance_score}/10 · 创新 {paper.innovation_score}/10</small></h2>
        <p><strong>研究动机：</strong>{html.escape(paper.research_motivation)}</p>
        <p><strong>核心贡献：</strong>{html.escape(paper.core_contributions)}</p>
        <div class="meta">{html.escape(authors)} · ArXiv · 综合分 {paper.combined_score:.1f}</div>
        </div></article>"""

    @staticmethod
    def _feed_errors_markdown(errors: dict[str, str]) -> list[str]:
        if not errors:
            return []
        return [f"> 部分数据源获取失败：{'、'.join(errors)}；其他来源不受影响。", ""]

    @staticmethod
    def _blog_markdown(post: TechBlogPost) -> list[str]:
        return ReportWriter._feed_markdown(
            post,
            f"相关性 **{post.relevance_score}/10** · 创新性 **{post.innovation_score}/10**",
        )

    @staticmethod
    def _news_markdown(post: TechNewsPost) -> list[str]:
        return ReportWriter._feed_markdown(
            post,
            f"相关性 **{post.relevance_score}/10** · 创新性 **{post.innovation_score}/10**",
        )

    @staticmethod
    def _feed_markdown(post: TechBlogPost | TechNewsPost, scores: str) -> list[str]:
        published = (
            post.published_at.astimezone(BEIJING).date().isoformat()
            if post.published_at
            else "未知"
        )
        keywords = "、".join(post.matched_keywords) or "无"
        return [
            f"### {post.pick_rank}. [{post.title}]({post.url})",
            "",
            f"{scores} · 综合分 **{post.final_score:.1f}**",
            "",
            f"> **推荐理由**：{post.recommendation_reason}",
            "",
            post.summary,
            "",
            f"**来源**：{post.source_name} · **发布日期**：{published} · **命中词**：{keywords}",
            "",
        ]

    @staticmethod
    def _blog_html(post: TechBlogPost) -> str:
        return ReportWriter._feed_html(
            post, f"相关 {post.relevance_score}/10 · 创新 {post.innovation_score}/10"
        )

    @staticmethod
    def _news_html(post: TechNewsPost) -> str:
        return ReportWriter._feed_html(
            post, f"相关 {post.relevance_score}/10 · 创新 {post.innovation_score}/10"
        )

    @staticmethod
    def _feed_html(post: TechBlogPost | TechNewsPost, scores: str) -> str:
        keywords = "、".join(post.matched_keywords) or "无"
        return f"""<article><div class="rank">{post.pick_rank}</div><div class="content">
        <h2><a href="{html.escape(post.url)}">{html.escape(post.title)}</a>
        <small>{html.escape(scores)}</small></h2>
        <p class="why"><strong>推荐理由：</strong>{html.escape(post.recommendation_reason)}</p>
        <p>{html.escape(post.summary)}</p>
        <div class="meta">{html.escape(post.source_name)} · 命中词 {html.escape(keywords)} · 综合分 {post.final_score:.1f}</div>
        </div></article>"""

    @staticmethod
    def _feed_section_html(cards: str, errors: dict[str, str], empty_message: str) -> str:
        warning = ""
        if errors:
            warning = (
                '<p class="risk">部分数据源获取失败：'
                + html.escape("、".join(errors))
                + "；其他来源不受影响。</p>"
            )
        return warning + (cards or f"<p>{html.escape(empty_message)}</p>")

    @staticmethod
    def _feed_digest(
        post: TechBlogPost | TechNewsPost, secondary_label: str, secondary_score: int
    ) -> list[str]:
        return [
            f"{post.pick_rank}. [相关 {post.relevance_score}/10 · {secondary_label} "
            f"{secondary_score}/10] {post.title}",
            f"推荐理由：{post.recommendation_reason}",
            post.summary[:120],
            post.url,
            "",
        ]
