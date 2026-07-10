from __future__ import annotations

import html
import json
from datetime import date
from pathlib import Path

from .config import ReportConfig
from .models import Repository


class ReportWriter:
    def __init__(self, config: ReportConfig) -> None:
        self.config = config

    def write(self, repositories: list[Repository], day: date) -> dict[str, Path]:
        output_dir = Path(self.config.output_dir) / day.isoformat()
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = {
            "markdown": output_dir / "daily.md",
            "html": output_dir / "daily.html",
            "json": output_dir / "daily.json",
        }
        paths["markdown"].write_text(self.markdown(repositories, day), encoding="utf-8")
        paths["html"].write_text(self.html(repositories, day), encoding="utf-8")
        paths["json"].write_text(
            json.dumps(
                {
                    "date": day.isoformat(),
                    "repositories": [item.to_dict() for item in repositories],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return paths

    def markdown(self, repositories: list[Repository], day: date) -> str:
        lines = [
            f"# {self.config.title}",
            "",
            f"> {day.isoformat()} · 今天只看这 {len(repositories)} 个",
            "",
            "根据你的关注词对 GitHub Trending 重新排序。分数表示与你的匹配程度，"
            "不是项目质量的绝对排名。",
            "",
        ]
        for item in repositories:
            lines.extend(
                [
                    f"## {item.pick_rank}. [{item.full_name}]({item.url})",
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
        lines.extend(
            [
                "---",
                "",
                "由 [RepoCourier](https://github.com/jjyaoao/repo-courier) 自动生成。",
                "",
            ]
        )
        return "\n".join(lines)

    def html(self, repositories: list[Repository], day: date) -> str:
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
        return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(self.config.title)}</title>
<style>body{{margin:0;background:#f6f8fa;color:#1f2328;font:15px/1.6 system-ui,sans-serif}}main{{max-width:900px;margin:auto;padding:32px 18px}}header{{padding:26px;background:#0d1117;color:white;border-radius:16px;margin-bottom:18px}}header h1{{margin:0 0 6px}}article{{display:flex;gap:18px;background:white;padding:24px;margin:14px 0;border:1px solid #d0d7de;border-radius:14px}}.rank{{font-size:32px;font-weight:800;color:#8250df}}.content{{flex:1}}h2{{margin:0}}h2 a{{color:#0969da;text-decoration:none}}small{{font-size:12px;background:#fbefff;color:#8250df;padding:3px 7px;border-radius:12px}}.why{{background:#f6f8ff;border-left:4px solid #8250df;padding:10px 12px}}.meta{{color:#59636e;margin:12px 0}}.columns{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}h3{{font-size:14px;margin-bottom:2px}}.risk{{background:#fff8c5;padding:8px 12px;border-radius:8px}}footer{{text-align:center;color:#656d76;padding:20px}}@media(max-width:600px){{.columns{{grid-template-columns:1fr}}article{{padding:16px}}}}</style></head>
<body><main><header><h1>{html.escape(self.config.title)}</h1><div>{day.isoformat()} · 今天只看这 {len(repositories)} 个</div></header>
{''.join(cards)}<footer>Generated by RepoCourier</footer></main></body></html>"""

    def digest(self, repositories: list[Repository], day: date, limit: int = 5) -> str:
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
        lines.append("少看榜单，多看真正与你有关的项目。")
        return "\n".join(lines)
