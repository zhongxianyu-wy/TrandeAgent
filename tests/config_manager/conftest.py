"""config_manager 测试公共夹具。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.config_manager.schema import AppConfig, ArenaSection
from src.screener.models import Rule as ScreenerRule
from src.signal.models import SignalRule


def _git(args: list[str], cwd: Path) -> str:
    """在指定目录执行 git 命令，返回 stdout。"""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    """初始化一个临时 git 仓库（含 user 配置），返回仓库根路径。"""
    _git(["init"], tmp_path)
    _git(["config", "user.email", "test@example.com"], tmp_path)
    _git(["config", "user.name", "Test User"], tmp_path)
    return tmp_path


def make_screener_rule(
    name: str = "r1",
    field: str = "l2_performance.sharpe",
    op: str = ">=",
    value: float = 1.0,
) -> ScreenerRule:
    return ScreenerRule(name=name, field=field, op=op, value=value)


def make_signal_rule(
    name: str = "均线金叉",
    category: str = "technical",
    indicator: str = "ma_cross",
    operator: str = "cross_above",
    threshold: float = 0.0,
    weight: float = 1.0,
) -> SignalRule:
    return SignalRule(
        name=name,
        category=category,
        indicator=indicator,
        operator=operator,
        threshold=threshold,
        weight=weight,
    )


def make_config(
    pool: list[str] | None = None,
    screener: list[ScreenerRule] | None = None,
    signals: list[SignalRule] | None = None,
    arena: ArenaSection | None = None,
) -> AppConfig:
    return AppConfig(
        observation_pool=pool or ["000001", "000002"],
        screener_rules=screener if screener is not None else [make_screener_rule()],
        signal_rules=signals if signals is not None else [make_signal_rule()],
        arena=arena or ArenaSection(),
    )


VALID_YAML = """\
observation_pool:
  - "000001"
  - "000002"
screener_rules:
  - name: "r1"
    field: "l2_performance.sharpe"
    op: ">="
    value: 1.0
signal_rules:
  - name: "均线金叉"
    category: "technical"
    indicator: "ma_cross"
    operator: "cross_above"
    threshold: 0
    weight: 1.0
arena:
  enabled: true
  strategy_count: 100
  backtest_years: 5
  top_n_per_domain: 5
"""
