"""pytest fixtures（Feature #8 strategy-arena）。

提供 mock LLM、构造的净值序列、样例策略，全程不依赖真实网络/LLM。
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from src.analyzer.llm.client import LLMClient
from src.arena.mind_models.loader import (
    load_arena_config,
    load_mind_model_dicts,
    load_prototype_dicts,
)
from src.arena.models import Strategy


# ---------- 净值序列 ----------

def make_nav(n: int = 252 * 5, *, seed: int = 42, drift: float = 0.0004, vol: float = 0.012) -> pd.Series:
    """构造一条 n 日、带漂移+噪声的日频净值序列（业务日历）。"""
    rng = np.random.default_rng(seed)
    ret = drift + vol * rng.standard_normal(n)
    ret[0] = 0.0
    nav = pd.Series(
        np.cumprod(1.0 + ret),
        index=pd.date_range("2021-01-04", periods=n, freq="B"),
    )
    nav.index.name = "trade_date"
    return nav


@pytest.fixture
def nav() -> pd.Series:
    return make_nav()


@pytest.fixture
def short_nav() -> pd.Series:
    """较短序列，用于触发滚动窗口不足的边界。"""
    return make_nav(n=120, seed=1)


# ---------- ground truth（配置）----------

@pytest.fixture(scope="session")
def prototype_dicts() -> list[dict]:
    return load_prototype_dicts()


@pytest.fixture(scope="session")
def mind_model_dicts() -> list[dict]:
    return load_mind_model_dicts()


@pytest.fixture(scope="session")
def arena_config() -> dict:
    return load_arena_config()


@pytest.fixture(scope="session")
def dim_matrix(arena_config) -> dict:
    return arena_config["dimension_matrix"]


# ---------- 样例策略 ----------

def make_strategy(
    *,
    strategy_id: str = "strat_test_01",
    prototype_id: str = "proto_ma_cross",
    domain: str = "趋势",
    params: dict | None = None,
    mind_model_id: str | None = None,
    **kw,
) -> Strategy:
    return Strategy(
        strategy_id=strategy_id,
        prototype_id=prototype_id,
        mind_model_id=mind_model_id,
        domain=domain,  # type: ignore[arg-type]
        params=params or {},
        source_explanation=kw.get("source_explanation", "测试策略"),
        timing_logic=kw.get("timing_logic", "技术面"),
        rebalance_freq=kw.get("rebalance_freq", "月"),
        risk_threshold=kw.get("risk_threshold", 0.10),
        concentration=kw.get("concentration", "Top10"),
    )


@pytest.fixture
def strategy() -> Strategy:
    return make_strategy()


@pytest.fixture
def strategies_multi_domain() -> list[Strategy]:
    """覆盖多个领域的样例策略集合，供排名器测试。"""
    out: list[Strategy] = []
    specs = [
        ("趋势", "proto_ma_cross", {"fast": 10, "slow": 30}),
        ("趋势", "proto_macd", {}),
        ("趋势", "proto_turtle", {}),
        ("价值", "proto_4433", {}),
        ("价值", "proto_pe_dca", {}),
        ("低波", "proto_dca", {}),
        ("低波", "proto_drawdown_recovery", {"threshold": 0.12}),
        ("成长", "proto_momentum_rotation", {}),
    ]
    for i, (d, pid, p) in enumerate(specs):
        out.append(make_strategy(strategy_id=f"s{i}", prototype_id=pid, domain=d, params=p))
    return out


# ---------- mock LLM ----------

class MockLLMClient(LLMClient):
    """按预设序列返回响应的 mock LLM。"""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls: list[tuple[str, str]] = []

    def analyze_fund(self, prompt: str, metrics_json: str) -> dict:
        self.calls.append((prompt, metrics_json))
        if not self._responses:
            return {"strategies": []}
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture
def mock_llm_factory():
    """返回构造 MockLLMClient 的工厂。"""
    return MockLLMClient


def valid_llm_strategy_payload(
    *,
    prototype_id: str = "proto_ma_cross",
    domain: str = "趋势",
    mind_model_id: str | None = "mind_buffett",
    sid: str = "strat_llm_01",
    extra_field: bool = False,
    invented_proto: bool = False,
    invented_mind: bool = False,
    params: dict | None = None,
) -> dict:
    """构造一个合法（或可配置为非法）的 LLM 返回策略 dict。

    params 默认按 prototype 选择其 params_template 内的合法键；可通过 params 覆盖。
    """
    _proto_params = {
        "proto_4433": {"short_window": 63, "mid_window": 126, "long_window": 252},
        "proto_dual_momentum": {"lookback_months": 12, "abs_window": 252, "rel_window": 63},
        "proto_grid": {"window": 60},
        "proto_dca": {},
        "proto_ma_cross": {"fast": 10, "slow": 30},
        "proto_macd": {"fast": 12, "slow": 26, "signal": 9},
        "proto_rsi_reversal": {"period": 14, "oversold": 30, "overbought": 70},
        "proto_bollinger_breakout": {"window": 20, "k": 2.0},
        "proto_drawdown_recovery": {"threshold": 0.15},
        "proto_pe_dca": {"window": 252, "high_pct": 0.8, "low_pct": 0.3},
        "proto_momentum_rotation": {"window": 60},
        "proto_low_vol": {},
        "proto_turtle": {"breakout_days": 20, "exit_days": 10},
        "proto_mean_reversion": {"window": 30, "threshold": 1.0},
        "proto_risk_parity": {},
    }
    chosen = dict(params) if params is not None else dict(_proto_params.get(prototype_id, {}))
    d = {
        "strategy_id": sid,
        "prototype_id": "proto_invented" if invented_proto else prototype_id,
        "mind_model_id": "mind_invented" if invented_mind else mind_model_id,
        "domain": domain,
        "params": chosen,
        "timing_logic": "技术面",
        "rebalance_freq": "月",
        "risk_threshold": 0.10,
        "concentration": "Top10",
        "source_explanation": "来源说明",
    }
    if extra_field:
        d["params"]["unknown_param"] = 999  # 不在 params_template 内
    return d
