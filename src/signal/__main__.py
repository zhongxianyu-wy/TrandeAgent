"""signal-engine CLI 入口（T12）。

用法：
    python -m src.signal calc --codes 000001,161725 [--config config/signals.yaml]
    python -m src.signal alert --code 000001 --return -4.0
    python -m src.signal demo           # 用样例净值演示信号（无需数据源）
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
from loguru import logger

from src.signal.engine import DefaultSignalEngine
from src.signal.fund_specific import DEFAULT_INTRADAY_ALERT_THRESHOLD
from src.signal.models import Signal, SignalRule

DEFAULT_CONFIG_PATH = "config/signals.yaml"


def load_rules(config_path: str | Path = DEFAULT_CONFIG_PATH) -> tuple[list[SignalRule], float]:
    """从 YAML 加载规则与大跌阈值。

    Returns:
        (rules, intraday_alert_threshold)
    """
    path = Path(config_path)
    if not path.exists():
        logger.warning("信号配置 {} 不存在，使用空规则", path)
        return [], DEFAULT_INTRADAY_ALERT_THRESHOLD
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    rules = [SignalRule(**r) for r in raw.get("rules", [])]
    threshold = float(raw.get("intraday_alert_threshold", DEFAULT_INTRADAY_ALERT_THRESHOLD))
    return rules, threshold


def _try_make_provider():
    """尝试用 AkShareProvider 构造真实数据源；失败返回 None。"""
    try:
        from src.data import load_data_config, setup_logging
        from src.data.akshare_provider import AkShareProvider

        config = load_data_config()
        setup_logging(config)
        return AkShareProvider(config)
    except Exception as e:  # noqa: BLE001
        logger.warning("无法初始化数据源，将使用 demo 模式：{}", e)
        return None


def _print_signals(signals: list[Signal]) -> None:
    if not signals:
        print("（无信号）")
        return
    print("=" * 70)
    print(f"{'基金代码':<12}{'日期':<14}{'档位':<6}{'得分':<8}理由")
    print("-" * 70)
    for s in signals:
        reasons = " | ".join(s.reasons) if s.reasons else "（无触发规则）"
        print(f"{s.fund_code:<12}{str(s.date):<14}{s.level:<6}{s.score:<8.2f}{reasons}")
    print("=" * 70)


def cmd_calc(args: argparse.Namespace) -> int:
    rules, threshold = load_rules(args.config)
    if not rules:
        print("无信号规则，请检查 config/signals.yaml")
        return 1
    codes = [c.strip() for c in args.codes.split(",") if c.strip()]
    provider = _try_make_provider()
    if provider is None:
        print("数据源不可用，请改用 demo 子命令或检查 config/data.yaml")
        return 2
    engine = DefaultSignalEngine(provider, intraday_threshold=threshold)
    try:
        signals = engine.calc_signals(codes, rules, end_date=date.today())
    finally:
        close = getattr(provider, "close", None)
        if callable(close):
            close()
    _print_signals(signals)
    return 0


def cmd_alert(args: argparse.Namespace) -> int:
    rules, threshold = load_rules(args.config)
    threshold = args.threshold if args.threshold is not None else threshold
    provider = _try_make_provider()
    engine = DefaultSignalEngine(provider, intraday_threshold=threshold) if provider else DefaultSignalEngine(intraday_threshold=threshold)  # type: ignore[arg-type]
    triggered = engine.detect_intraday_alert(args.code, args.return_value)
    print(
        f"基金 {args.code} 单日 {args.return_value:.2f}% "
        f"阈值 {threshold:.2f}% → {'触发大跌警报' if triggered else '未触发'}"
    )
    return 0 if not triggered else 0


def _make_demo_provider(today: date, start: date):
    """构造一个返回上涨/下跌/震荡三条净值序列的内存 DataProvider。"""
    import numpy as np
    from src.data.provider import DataProvider

    dates = pd.date_range(start=start, end=today, freq="B")
    n = len(dates)
    rng = np.random.default_rng(7)
    up = np.exp(np.cumsum(rng.normal(0.0012, 0.01, n)))
    down = np.exp(np.cumsum(rng.normal(-0.0012, 0.01, n)))
    flat = np.exp(np.cumsum(rng.normal(0.0, 0.008, n)))

    def _to_df(nav: np.ndarray) -> pd.DataFrame:
        rets = pd.Series(nav).pct_change().fillna(0).to_numpy() * 100.0
        return pd.DataFrame({
            "trade_date": dates.date,
            "unit_nav": np.round(nav, 4),
            "accum_nav": np.round(nav, 4),
            "daily_return": np.round(rets, 4),
            "is_adjusted": True,
        })

    nav_map = {"DEMO_UP": _to_df(up), "DEMO_DOWN": _to_df(down), "DEMO_FLAT": _to_df(flat)}

    class _DemoProvider(DataProvider):
        def list_funds(self, categories=None) -> pd.DataFrame:
            return pd.DataFrame()

        def get_nav(self, fund_code: str, start_d: date, end_d: date) -> pd.DataFrame:
            return nav_map.get(fund_code, pd.DataFrame())

        def get_manager(self, fund_code: str) -> pd.DataFrame:
            return pd.DataFrame()

        def get_holdings(self, fund_code: str, report_date=None) -> pd.DataFrame:
            return pd.DataFrame()

        def refresh_incremental(self, fund_codes=None) -> dict:
            return {}

        def refresh_full_backfill(self, fund_codes, years: int = 5) -> dict:
            return {}

        def get_freshness_report(self) -> pd.DataFrame:
            return pd.DataFrame()

    return _DemoProvider()


def cmd_demo(args: argparse.Namespace) -> int:
    """用样例净值序列（上涨/下跌/震荡）演示信号，不依赖数据源。"""
    rules, threshold = load_rules(args.config)
    if not rules:
        rules = _demo_rules()

    today = date.today()
    start = today - timedelta(days=400)
    provider = _make_demo_provider(today, start)
    engine = DefaultSignalEngine(provider, intraday_threshold=threshold)
    codes = ["DEMO_UP", "DEMO_DOWN", "DEMO_FLAT"]
    signals = engine.calc_signals(codes, rules, end_date=today)
    _print_signals(signals)
    return 0


def _demo_rules() -> list[SignalRule]:
    return [
        SignalRule(name="均线金叉", category="technical", indicator="ma_cross",
                   operator="cross_above", threshold=0, weight=1.0),
        SignalRule(name="均线死叉", category="technical", indicator="ma_cross",
                   operator="cross_below", threshold=0, weight=1.0),
        SignalRule(name="MACD金叉", category="technical", indicator="macd",
                   operator="cross_above", threshold=0, weight=1.0),
        SignalRule(name="RSI超卖", category="technical", indicator="rsi",
                   operator="below", threshold=30, weight=0.8),
        SignalRule(name="RSI超买", category="technical", indicator="rsi",
                   operator="above", threshold=70, weight=0.8),
        SignalRule(name="布林下轨", category="technical", indicator="bollinger",
                   operator="below", threshold=2.0, weight=0.8),
        SignalRule(name="PE低估", category="fundamental", indicator="pe_percentile",
                   operator="below", threshold=20, weight=1.0),
        SignalRule(name="回撤补仓", category="fundamental", indicator="drawdown",
                   operator="below", threshold=-10.0, weight=1.2),
        SignalRule(name="大跌警报", category="fund_specific", indicator="intraday_alert",
                   operator="below", threshold=-3.0, weight=2.0),
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="src.signal", description="择时信号引擎 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_calc = sub.add_parser("calc", help="批量计算信号")
    p_calc.add_argument("--codes", required=True, help="逗号分隔的基金代码")
    p_calc.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="信号规则 YAML 路径")

    p_alert = sub.add_parser("alert", help="大跌即时检测")
    p_alert.add_argument("--code", required=True, help="基金代码")
    p_alert.add_argument("--return", dest="return_value", type=float, required=True,
                         help="单日涨跌幅（百分比，如 -4.0）")
    p_alert.add_argument("--threshold", type=float, default=None, help="覆盖大跌阈值")
    p_alert.add_argument("--config", default=DEFAULT_CONFIG_PATH)

    p_demo = sub.add_parser("demo", help="用样例净值演示信号（无需数据源）")
    p_demo.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="信号规则 YAML 路径")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "calc":
        return cmd_calc(args)
    if args.command == "alert":
        return cmd_alert(args)
    if args.command == "demo":
        return cmd_demo(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
