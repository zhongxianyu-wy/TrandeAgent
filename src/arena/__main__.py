"""策略竞技场 CLI（T17）。

用法：
    python -m src.arena run --count 100 --fund-code 110011

注意：真实运行需要 LLM 与历史净值数据。本 CLI 仅做最小编排，LLM/数据由
调用方注入；测试通过 mock 上游完成。
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="src.arena", description="策略竞技场")
    sub = p.add_subparsers(dest="command", required=True)

    run_p = sub.add_parser("run", help="运行竞技场全流程")
    run_p.add_argument("--count", type=int, default=100, help="生成策略数")
    run_p.add_argument("--fund-code", type=str, default="110011", help="基准基金代码")
    run_p.add_argument("--years", type=int, default=5, help="回测年数")
    run_p.add_argument("--write-base", action="store_true", help="写入飞书 Base（需配置）")
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        logger.info(
            "竞技场 run：count={} fund_code={} years={}",
            args.count,
            args.fund_code,
            args.years,
        )
        # 真实编排需要注入 DataProvider 与 LLMClient，此处仅占位提示。
        logger.warning(
            "CLI 占位：真实运行请通过 ArenaPipeline 注入 DataProvider + LLMClient。"
        )
        print("竞技场 CLI 占位 —— 请用 ArenaPipeline 编排真实数据/LLM。")
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
