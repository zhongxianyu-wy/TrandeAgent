"""生成示例配置（T11）。

首次运行生成 ``config/strategies.yaml.example``，包含各模块的代表性配置。
"""
from __future__ import annotations

from pathlib import Path

from src.config_manager.loader import dump_config_yaml
from src.config_manager.schema import AppConfig, ArenaSection
from src.screener.models import Rule as ScreenerRule
from src.signal.models import SignalRule

_EXAMPLE_HEADER = """\
# 策略配置（Feature #9 config-manager）
#
# 集中管理：观察池 / 筛选规则 / 信号规则 / 竞技场配置。
# 支持 ${VAR} 环境变量替换（如 ${MY_API_KEY}）。
# 使用 `python -m src.config_manager validate <file>` 校验。

"""


def build_example_config() -> AppConfig:
    """构建示例 :class:`AppConfig`。"""
    return AppConfig(
        observation_pool=["000001", "110011", "519066"],
        screener_rules=[
            ScreenerRule(
                name="return_1y_top33",
                field="l2_performance.return_1y",
                op="percentile_top",
                value=0.33,
            ),
            ScreenerRule(
                name="scale_2_to_50",
                field="l1_basic.scale",
                op="between",
                value=[2.0, 50.0],
            ),
            ScreenerRule(
                name="sharpe_top25",
                field="l2_performance.sharpe",
                op="percentile_top",
                value=0.25,
            ),
        ],
        signal_rules=[
            SignalRule(
                name="均线金叉",
                category="technical",
                indicator="ma_cross",
                operator="cross_above",
                threshold=0,
                weight=1.0,
            ),
            SignalRule(
                name="RSI超卖",
                category="technical",
                indicator="rsi",
                operator="below",
                threshold=30,
                weight=0.8,
            ),
            SignalRule(
                name="PE历史低估",
                category="fundamental",
                indicator="pe_percentile",
                operator="below",
                threshold=20,
                weight=1.0,
            ),
            SignalRule(
                name="大跌警报",
                category="fund_specific",
                indicator="intraday_alert",
                operator="below",
                threshold=-3.0,
                weight=2.0,
            ),
        ],
        arena=ArenaSection(
            enabled=True,
            strategy_count=100,
            backtest_years=5,
            top_n_per_domain=5,
        ),
    )


def generate_example() -> str:
    """返回示例配置 YAML 文本（含注释头）。"""
    return _EXAMPLE_HEADER + dump_config_yaml(build_example_config())


def write_example(path: str | Path) -> Path:
    """把示例配置写入文件，返回文件路径。"""
    p = Path(path)
    p.write_text(generate_example(), encoding="utf-8")
    return p
