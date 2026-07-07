"""策略去重器（T07）。

用纯 numpy 计算 cosine 距离，参数空间距离 < 阈值（默认 0.1）视为同质化剔除。
不依赖 scikit-learn（Python 3.13 兼容性）。

特征向量构造：one-hot 编码 prototype(15) + domain(8) + 择时(4) + 频率(4) +
集中度(4) + risk_threshold(1, 全局归一化) + 已知参数槽(全局归一化)。
- 不同 prototype → 向量在原型维度完全不重叠 → 余弦距离大，绝不误去重
- 完全相同的策略 → 向量相同 → 距离 0，正确去重
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.arena.models import DOMAINS, Strategy
from src.arena.strategies import list_prototype_ids

# 差异维度的合法取值（与 arena.yaml dimension_matrix 对齐）
TIMING_LOGICS = ("技术面", "基本面", "技术+基本", "无择时")
REBALANCE_FREQS = ("周", "双周", "月", "季")
CONCENTRATIONS = ("Top5", "Top10", "Top20", "Top50")

# 已知参数键的全局归一化范围 [lo, hi]（覆盖 15 个原型的参数空间）
PARAM_SCHEMA: dict[str, tuple[float, float]] = {
    "fast": (5.0, 120.0),
    "slow": (5.0, 250.0),
    "signal": (5.0, 30.0),
    "window": (5.0, 252.0),
    "short_window": (5.0, 252.0),
    "mid_window": (5.0, 252.0),
    "long_window": (5.0, 504.0),
    "period": (2.0, 60.0),
    "threshold": (0.01, 0.5),
    "k": (0.5, 3.0),
    "oversold": (10.0, 40.0),
    "overbought": (60.0, 90.0),
    "high_pct": (0.5, 0.95),
    "low_pct": (0.05, 0.5),
    "breakout_days": (5.0, 60.0),
    "exit_days": (5.0, 30.0),
    "lookback_months": (1.0, 24.0),
    "abs_window": (21.0, 504.0),
    "rel_window": (10.0, 252.0),
}


def _one_hot(value: Any, options: tuple[str, ...]) -> list[float]:
    return [1.0 if value == opt else 0.0 for opt in options]


def _risk_norm(v: Any) -> float:
    if v is None:
        return 0.5
    try:
        return (float(v) - 0.05) / (0.20 - 0.05)  # 0.05~0.20 -> 0~1
    except (TypeError, ValueError):
        return 0.5


def _param_features(params: dict) -> list[float]:
    """按固定 PARAM_SCHEMA 顺序输出全局归一化参数槽；缺失键用 0.5（中性）。"""
    feats: list[float] = []
    for key, (lo, hi) in PARAM_SCHEMA.items():
        val = params.get(key)
        if isinstance(val, (int, float)):
            span = hi - lo
            feats.append((float(val) - lo) / span if span > 0 else 0.5)
        else:
            feats.append(0.5)
    return feats


def strategy_to_vector(strategy: Strategy) -> np.ndarray:
    """把 Strategy 编码为定长 one-hot + 归一化特征向量。

    维度 = 15(原型) + 8(领域) + 4(择时) + 4(频率) + 4(集中度) + 1(风控)
           + len(PARAM_SCHEMA)(参数槽)，全为定长。
    """
    proto_ids = tuple(list_prototype_ids())
    feats: list[float] = []
    feats.extend(_one_hot(strategy.prototype_id, proto_ids))
    feats.extend(_one_hot(strategy.domain, DOMAINS))
    feats.extend(_one_hot(strategy.timing_logic, TIMING_LOGICS))
    feats.extend(_one_hot(strategy.rebalance_freq, REBALANCE_FREQS))
    feats.extend(_one_hot(strategy.concentration, CONCENTRATIONS))
    feats.append(_risk_norm(strategy.risk_threshold))
    feats.extend(_param_features(strategy.params))
    return np.array(feats, dtype=float)


def vector_length() -> int:
    """特征向量的固定长度（测试/调试用）。"""
    proto_ids = tuple(list_prototype_ids())
    return (
        len(proto_ids)
        + len(DOMAINS)
        + len(TIMING_LOGICS)
        + len(REBALANCE_FREQS)
        + len(CONCENTRATIONS)
        + 1  # risk_threshold
        + len(PARAM_SCHEMA)
    )


def cosine_distance(a: np.ndarray, b: np.ndarray) -> float:
    """余弦距离 = 1 - cosine相似度，范围 [0,2]。零向量距离定义为 1.0。"""
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return 1.0
    sim = float(np.dot(a, b) / (na * nb))
    sim = max(-1.0, min(1.0, sim))  # 数值稳健
    return 1.0 - sim


class CosineDeduplicator:
    """基于参数空间 cosine 距离的贪婪去重器。"""

    def __init__(
        self,
        *,
        domains: tuple[str, ...] = DOMAINS,
        timing_logics: tuple[str, ...] = TIMING_LOGICS,
        rebalance_freqs: tuple[str, ...] = REBALANCE_FREQS,
        concentrations: tuple[str, ...] = CONCENTRATIONS,
    ) -> None:
        self.domains = domains
        self.timing_logics = timing_logics
        self.rebalance_freqs = rebalance_freqs
        self.concentrations = concentrations

    def deduplicate(
        self, strategies: list[Strategy], threshold: float = 0.1
    ) -> list[Strategy]:
        """保留每个等价类中的首个策略，距离 < threshold 视为重复。

        Args:
            strategies: 待去重策略列表（顺序即优先级）。
            threshold: 重复判定阈值（cosine 距离），默认 0.1。
        """
        if threshold < 0:
            raise ValueError(f"去重阈值必须 >= 0，得到：{threshold}")
        kept: list[Strategy] = []
        kept_vecs: list[np.ndarray] = []
        for s in strategies:
            vec = strategy_to_vector(s)
            is_dup = False
            for kv in kept_vecs:
                if cosine_distance(vec, kv) < threshold:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(s)
                kept_vecs.append(vec)
        return kept

    @staticmethod
    def pairwise_distance(s1: Strategy, s2: Strategy) -> float:
        """工具方法：计算两策略的 cosine 距离。"""
        return cosine_distance(strategy_to_vector(s1), strategy_to_vector(s2))
