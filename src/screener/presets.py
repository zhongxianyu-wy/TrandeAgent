"""预置规则集（T10）。

提供 4433 法则等开箱即用的 ScreenerConfig，同时支持从 config/screener.yaml
加载命名预设。4433 法则：近期业绩排名前 1/3~1/4，多周期 + 风险调整收益。
"""
from __future__ import annotations

from pathlib import Path

from src.screener.models import Rule, ScreenerConfig, load_yaml_presets

# 默认配置文件位置（相对项目根）
DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "screener.yaml"


def preset_4433() -> ScreenerConfig:
    """4433 法则预设（程序化定义，便于测试）。

    多周期业绩同类排名前 1/3~1/4 + 风险调整收益维度。
    字段路径用嵌套写法（与 FundIndicators 对应），engine 会自动适配扁平列名。
    """
    return ScreenerConfig(
        rules=[
            Rule(
                name="return_1y_top33",
                field="l2_performance.return_1y",
                op="percentile_top",
                value=0.33,
            ),
            Rule(
                name="return_3y_top33",
                field="l2_performance.return_3y",
                op="percentile_top",
                value=0.33,
            ),
            Rule(
                name="return_5y_top25",
                field="l2_performance.return_5y",
                op="percentile_top",
                value=0.25,
            ),
            Rule(
                name="sharpe_top25",
                field="l2_performance.sharpe",
                op="percentile_top",
                value=0.25,
            ),
            Rule(
                name="scale_2_to_50",
                field="l1_basic.scale",
                op="between",
                value=[2.0, 50.0],
            ),
        ],
        weights={
            "return_1y_top33": 1.0,
            "return_3y_top33": 1.0,
            "return_5y_top25": 1.5,
            "sharpe_top25": 1.5,
            "scale_2_to_50": 0.5,
        },
        top_n=20,
    )


def preset_quality() -> ScreenerConfig:
    """聪明钱/高质量预设：机构青睐 + 经理稳定 + 回撤可控。"""
    return ScreenerConfig(
        rules=[
            Rule(
                name="institution_holding_ge30",
                field="l1_basic.institution_holding_pct",
                op=">=",
                value=0.30,
            ),
            Rule(
                name="manager_tenure_ge2",
                field="l1_basic.manager_tenure_years",
                op=">=",
                value=2.0,
            ),
            Rule(
                name="max_drawdown_ge_neg25",
                field="l2_performance.max_drawdown",
                op=">=",
                value=-0.25,
            ),
            Rule(
                name="sharpe_ge05",
                field="l2_performance.sharpe",
                op=">=",
                value=0.5,
            ),
        ],
        weights={
            "institution_holding_ge30": 1.5,
            "manager_tenure_ge2": 1.0,
            "max_drawdown_ge_neg25": 1.0,
            "sharpe_ge05": 1.5,
        },
        top_n=20,
    )


# 程序化预设注册表
PRESETS: dict[str, ScreenerConfig] = {
    "rule_4433": preset_4433(),
    "quality": preset_quality(),
}


def get_preset(name: str, config_path: str | Path | None = None) -> ScreenerConfig:
    """取命名预设：优先 YAML 配置，回退到程序化预设。

    Args:
        name: 预设名（如 "rule_4433"）。
        config_path: screener.yaml 路径；None 用默认路径。
    """
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    if path.exists():
        try:
            yaml_presets = load_yaml_presets(path)
            if name in yaml_presets:
                return yaml_presets[name]
        except Exception:  # noqa: BLE001
            pass
    if name in PRESETS:
        return PRESETS[name]
    available = ", ".join(sorted(PRESETS))
    raise KeyError(f"找不到预设 '{name}'（可用程序化预设：{available}）")
