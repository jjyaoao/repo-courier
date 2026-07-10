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
        description="抓取、总结并投递 GitHub Trending 日报",
    )
    parser.add_argument("--config", default="config/config.yaml", help="YAML 配置文件路径")
    parser.add_argument("--date", help="报告日期，格式 YYYY-MM-DD，默认今天")
    parser.add_argument("--dry-run", action="store_true", help="生成报告但不发送消息")
    parser.add_argument("--verbose", action="store_true", help="显示调试日志")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )
    try:
        report_day = date.fromisoformat(args.date) if args.date else None
        result = run(load_config(args.config), day=report_day, dry_run=args.dry_run)
    except (OSError, ValueError, RuntimeError, httpx.HTTPError) as exc:
        logging.getLogger(__name__).error("运行失败: %s", exc)
        return 1
    print(f"完成：扫描 {result.scanned_count} 个项目，为你精选 {len(result.repositories)} 个")
    print(f"Markdown：{result.report_paths['markdown']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
