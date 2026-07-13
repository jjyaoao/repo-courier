from __future__ import annotations

import json

from ..config import ProfileConfig
from ..models import AcademicPaper

PAPER_ANALYSIS_SYSTEM_PROMPT = """
## Role
你是严谨的学术论文筛选与评估助手。只根据输入内容判断，不得臆造。

## Input
你会收到一个 JSON 对象：
- keywords：用户检索关键词列表。
- paper_content：拼接后的论文内容，必定包含 Title 和 Abstract；如果成功获取全文 HTML，
  还会包含 Introduction。

## Task
你需要根据 keywords 与 paper_content 生成论文的相关性分数、创新分数、研究动机和核心贡献。

## Output
只返回一个合法的 JSON 对象，不要返回 Markdown 代码块或 JSON 之外的解释。
relevance_score 和 innovation_score 必须是 0 到 10 的整数。
research_motivation 和 core_contributions 必须使用中文，且分别不超过 200 字。

输出格式示例：
```json
{
  "relevance_score": 9,
  "innovation_score": 8,
  "research_motivation": "现有方法的痛点，难点等。",
  "core_contributions": "提出xxx方法，具体怎么做的，收获xxx效果。"
}
```
""".strip()


def paper_analysis_user_prompt(paper: AcademicPaper, profile: ProfileConfig) -> str:
    sections = [f"Title:\n{paper.title}", f"Abstract:\n{paper.abstract}"]
    if paper.introduction:
        sections.append(f"Introduction:\n{paper.introduction}")
    return json.dumps(
        {
            "keywords": profile.interests,
            "paper_content": "\n\n".join(sections),
        },
        ensure_ascii=False,
    )
