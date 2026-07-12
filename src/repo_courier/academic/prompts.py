from __future__ import annotations

import json

from ..config import ProfileConfig
from ..models import AcademicPaper

PAPER_ANALYSIS_SYSTEM_PROMPT = (
    "你是严谨的学术论文筛选助手。只根据输入内容判断，不得臆造。"
    "只返回 JSON 对象，字段必须为 relevance_score、innovation_score、summary。"
    "两个分数必须是 0 到 10 的整数。"
    "summary 必须使用简洁中文，总结该篇论文所提出的与用户关键词相关的方法与创新点，"
    "不得扩展无关内容，不得超过 200 个字符。"
    "不要返回 Markdown 代码块或 JSON 之外的解释。"
    "输出格式示例："
    '{"relevance_score": 9, "innovation_score": 8, '
    '"summary": "总结该篇论文所提出的与关键词相关的方法与创新点。"}'
)


def paper_analysis_user_prompt(paper: AcademicPaper, profile: ProfileConfig) -> str:
    return json.dumps(
        {
            "keywords": profile.interests,
            "title": paper.title,
            "abstract": paper.abstract,
            "introduction": paper.introduction,
        },
        ensure_ascii=False,
    )
