from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import httpx

from .config import AppConfig, load_config
from .runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-courier",
        description="抓取、筛选并投递 GitHub Trending、RSS 科技专题与微信公众号文章",
    )
    parser.add_argument("--config", default="config/config.yaml", help="YAML 配置文件路径")
    parser.add_argument(
        "--date",
        help="RSS 与微信公众号检索日期，格式 YYYY-MM-DD，默认北京时间昨天",
    )
    parser.add_argument("--dry-run", action="store_true", help="生成报告但不发送消息")
    parser.add_argument(
        "--channels",
        help="仅运行指定通道，逗号分隔；可选 github、wechat 和 RSS 专题，all 运行全部",
    )
    parser.add_argument("--verbose", action="store_true", help="显示调试日志")
    return parser


def parse_channels(raw: str | None, config: AppConfig) -> list[str] | None:
    if raw is None:
        return None
    values = [value.strip() for value in raw.split(",")]
    if not values or any(not value for value in values):
        raise ValueError("--channels 不能为空或包含空专题名")
    available_channels = ["github", *config.rss.channels, "wechat"]
    if values == ["all"]:
        return available_channels
    if "all" in values:
        raise ValueError("--channels all 不能与其他专题同时使用")
    duplicates = sorted({value for value in values if values.count(value) > 1})
    if duplicates:
        raise ValueError(f"--channels 包含重复专题: {', '.join(duplicates)}")
    unknown = [value for value in values if value not in available_channels]
    if unknown:
        available = ", ".join(available_channels)
        raise ValueError(f"未知通道: {', '.join(unknown)}；可选值: {available}")
    return values


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        config = load_config(args.config)
        selected_channels = parse_channels(args.channels, config)
        report_day = date.fromisoformat(args.date) if args.date else None
        result = run(
            config,
            day=report_day,
            dry_run=args.dry_run,
            channels=selected_channels,
        )
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        logging.getLogger(__name__).error("运行失败: %s", exc)
        return 1
    details = "；".join(
        f"{channel.title}：扫描 {channel.scanned_count}、LLM候选 "
        f"{channel.llm_candidate_count}、入选 {len(channel.items)}"
        for channel in result.rss_channels.values()
    )
    github_detail = (
        f"扫描 {result.scanned_count} 个 GitHub 项目" if result.ran_github else "GitHub 未启用"
    )
    print(f"完成：{github_detail}" + (f"；{details}" if details else ""))
    print(f"Markdown：{result.report_paths['markdown']}")
    print(f"HTML：{result.report_paths['html']}")
    print(f"JSON：{result.report_paths['json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
