from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import httpx

from .config import load_config
from .runner import run


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-courier",
        description="抓取、总结并投递 GitHub Trending 与学术论文日报",
    )
    parser.add_argument("--config", default="config/config.yaml", help="YAML 配置文件路径")
    parser.add_argument(
        "--date",
        help="报告及论文检索日期，格式 YYYY-MM-DD，默认北京时间昨天",
    )
    parser.add_argument("--dry-run", action="store_true", help="生成报告但不发送消息")
    parser.add_argument(
        "--academic-only",
        action="store_true",
        help="只运行 Academic 流水线，跳过所有 GitHub 检索和历史读写",
    )
    parser.add_argument("--verbose", action="store_true", help="显示调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    # Keep verbose mode useful for RepoCourier without flooding the terminal with
    # socket/TLS state transitions from the HTTP stack.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        report_day = date.fromisoformat(args.date) if args.date else None
        result = run(
            load_config(args.config),
            day=report_day,
            dry_run=args.dry_run,
            academic_only=args.academic_only,
        )
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        logging.getLogger(__name__).error("运行失败: %s", exc)
        return 1
    print(
        f"完成：扫描 {result.scanned_count} 个项目和 {result.academic_scanned_count} 篇论文，"
        f"精选 {len(result.repositories)} 个项目和 {len(result.papers)} 篇论文"
    )
    print(f"Markdown：{result.report_paths['markdown']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
