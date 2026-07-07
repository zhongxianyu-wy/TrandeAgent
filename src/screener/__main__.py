"""基金筛选 CLI 入口（T11）。

用法：
    python -m src.screener run                          # 用 config/screener.yaml 默认规则
    python -m src.screener run --top 20                 # 指定 Top-N
    python -m src.screener run --preset rule_4433       # 用命名预设
    python -m src.screener run --rules custom.yaml      # 用自定义规则文件
    python -m src.screener presets                      # 列出可用预设
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from loguru import logger

from src.screener.engine import DefaultScreener
from src.screener.models import ScreenerConfig, load_yaml_config
from src.screener.presets import DEFAULT_CONFIG_PATH, PRESETS, get_preset

DEFAULT_TOP_N = 20


def resolve_config(args: argparse.Namespace) -> ScreenerConfig:
    """根据 CLI 参数解析筛选配置。"""
    if getattr(args, "rules", None):
        return load_yaml_config(args.rules)
    if getattr(args, "preset", None):
        return get_preset(args.preset)
    return load_yaml_config(DEFAULT_CONFIG_PATH)


def build_provider():
    """构造 DataProvider（惰性导入，便于测试隔离）。"""
    from src.data import load_data_config
    from src.data.akshare_provider import AkShareProvider

    config = load_data_config()
    return AkShareProvider(config)


def build_engine(provider, years: int = 5):
    """构造 IndicatorEngine（惰性导入，便于测试隔离）。"""
    import numpy as np

    from src.indicators import DefaultIndicatorEngine

    # 简单基准收益序列（实际场景可从 provider 注入）
    benchmark = np.random.default_rng(7).normal(0.0002, 0.01, 300)
    return DefaultIndicatorEngine(
        provider, benchmark_returns=benchmark, max_workers=8
    )


def run_screen(
    config: ScreenerConfig,
    provider=None,
    engine=None,
    end: date | None = None,
    years: int = 5,
    categories: list[str] | None = None,
) -> pd.DataFrame:
    """端到端筛选：拉基金清单 → 批量算指标 → 规则筛选打分。

    provider / engine 可注入（测试用），默认构造真实实现。
    """
    own_provider = provider is None
    if provider is None:
        provider = build_provider()
    if engine is None:
        engine = build_engine(provider, years=years)

    try:
        funds = provider.list_funds(categories=categories)
        if funds.empty:
            logger.warning("基金清单为空，无内容可筛选")
            return pd.DataFrame(
                columns=["fund_code", "score", "matched_rules", "reason"]
            )
        codes = funds["fund_code"].astype(str).tolist()
        end = end or date.today()
        indicators = engine.calc_batch(codes, end, years=years)
        if indicators.empty:
            logger.warning("指标计算结果为空")
            return pd.DataFrame(
                columns=["fund_code", "score", "matched_rules", "reason"]
            )
        screener = DefaultScreener()
        return screener.screen(config, indicators)
    finally:
        if own_provider and hasattr(provider, "close"):
            provider.close()


def _print_results(result: pd.DataFrame) -> None:
    if result.empty:
        print("无候选基金（请检查规则或数据）。")
        return
    print("=" * 60)
    print(f"筛选完成：{len(result)} 只候选基金")
    print("=" * 60)
    for _, row in result.iterrows():
        print(f"\n[{row['fund_code']}] 得分 {row['score']:.2f}")
        print(f"  理由：{row['reason']}")


def cmd_run(args: argparse.Namespace) -> int:
    config = resolve_config(args)
    if args.top:
        config = config.model_copy(update={"top_n": args.top})
    result = run_screen(
        config,
        end=_parse_date(args.end),
        years=args.years,
        categories=_parse_categories(args.categories),
    )
    _print_results(result)
    return 0


def cmd_presets(args: argparse.Namespace) -> int:
    print("可用预设：")
    # 合并程序化预设与 YAML 预设名
    names = set(PRESETS)
    if DEFAULT_CONFIG_PATH.exists():
        try:
            from src.screener.models import load_yaml_presets

            names |= set(load_yaml_presets(DEFAULT_CONFIG_PATH))
        except Exception:  # noqa: BLE001
            pass
    for name in sorted(names):
        print(f"  - {name}")
    return 0


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    return date.fromisoformat(s)


def _parse_categories(s: str | None) -> list[str] | None:
    if not s:
        return None
    return [c.strip() for c in s.split(",") if c.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="src.screener", description="基金筛选器 CLI"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="运行筛选")
    p_run.add_argument("--top", type=int, help="Top-N，覆盖配置")
    p_run.add_argument("--rules", help="自定义规则 YAML 文件路径")
    p_run.add_argument("--preset", help="命名预设（如 rule_4433）")
    p_run.add_argument("--end", help="截止日期 YYYY-MM-DD，默认今天")
    p_run.add_argument("--years", type=int, default=5, help="回溯年数")
    p_run.add_argument("--categories", help="基金大类逗号分隔，默认全部")
    p_run.set_defaults(func=cmd_run)

    p_presets = sub.add_parser("presets", help="列出可用预设")
    p_presets.set_defaults(func=cmd_presets)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
