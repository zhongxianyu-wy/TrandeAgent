"""综合合成 + 去噪（T10-T11）。

- synthesize：把多条规则明细加权合成一个 Signal（四档：加仓/持有/减仓/止损）。
- denoise：24h 内同基金同档位信号合并为一条，reasons 累加去重。
"""
from __future__ import annotations

from datetime import date, timedelta

from src.signal.models import Signal, SignalLevel


def score_to_level(score: float) -> SignalLevel:
    """加权得分 → 四档信号。

    规则（plan §synthesizer 综合合成）：
    - score < -1.0 → 止损
    - score < -0.5 → 减仓
    - score > 0.5  → 加仓
    - 其余         → 持有
    """
    if score < -1.0:
        return "止损"
    if score < -0.5:
        return "减仓"
    if score > 0.5:
        return "加仓"
    return "持有"


def synthesize(
    details: list[dict],
    weights: dict[str, float] | None = None,
    *,
    fund_code: str,
    date: date,
) -> Signal:
    """T10：多信号加权 → 综合评级。

    评分规则：
    - 触发的加仓信号贡献 +weight，减仓信号贡献 -weight
    - 权重优先取 weights[indicator]，否则取明细自带的 weight

    Args:
        details: 各规则评估器返回的明细 dict 列表。
        weights: 指标→权重映射（通常来自 SignalRule 列表），可空。
        fund_code: 基金代码。
        date: 信号日期。
    """
    weights = weights or {}
    score = 0.0
    reasons: list[str] = []
    for d in details:
        if not d.get("triggered"):
            continue
        w = weights.get(d.get("indicator", ""), d.get("weight", 1.0))
        direction = d.get("direction")
        if direction == "加仓":
            score += w
        elif direction == "减仓":
            score -= w
        reason = d.get("reason")
        if reason:
            reasons.append(reason)

    score = round(score, 4)
    level = score_to_level(score)
    return Signal(
        fund_code=fund_code,
        date=date,
        level=level,
        reasons=reasons,
        score=score,
        signals_detail=details,
    )


def _merge_two(a: Signal, b: Signal) -> Signal:
    """合并两个同基金同档位信号：保留最新日期，reasons 去重累加，明细拼接。"""
    seen: set[str] = set()
    reasons: list[str] = []
    for r in a.reasons + b.reasons:
        if r not in seen:
            seen.add(r)
            reasons.append(r)
    details = list(a.signals_detail) + list(b.signals_detail)
    latest = a if a.date >= b.date else b
    return Signal(
        fund_code=b.fund_code,
        date=max(a.date, b.date),
        level=b.level,
        reasons=reasons,
        score=latest.score,
        signals_detail=details,
    )


def denoise(signals: list[Signal], window_hours: int = 24) -> list[Signal]:
    """T11：去噪——window 内同基金同档位信号合并为一条。

    单日波动不重复推送（plan §FR-5）。signals 按 (fund_code, level, date) 排序后，
    若相邻同组信号日期差 <= window_hours/24 天则合并。

    Args:
        signals: 待去噪的信号列表。
        window_hours: 合并窗口（小时），默认 24。
    """
    if not signals:
        return []
    window_days = max(1, window_hours // 24)
    ordered = sorted(signals, key=lambda s: (s.fund_code, s.level, s.date))
    merged: list[Signal] = []
    for s in ordered:
        if merged:
            last = merged[-1]
            same_group = (
                last.fund_code == s.fund_code
                and last.level == s.level
                and (s.date - last.date).days <= window_days
            )
            if same_group:
                merged[-1] = _merge_two(last, s)
                continue
        merged.append(s.model_copy())
    return merged


def is_within_window(a: date, b: date, window_hours: int = 24) -> bool:
    """两日期是否在 window 小时内（按整天折算）。"""
    return abs((a - b).days) <= max(1, window_hours // 24)
