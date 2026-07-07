"""技术面信号（T03-T06）。

纯 pandas 实现 MA/MACD/RSI/布林带，不依赖 pandas-ta（plan §1 技术约束）。
每个 eval_xxx 接收净值序列 + SignalRule，返回一个明细 dict：

    {
        "name": str,            # 规则名
        "category": str,        # technical
        "indicator": str,       # ma_cross / macd / rsi / bollinger
        "value": Any,           # 最新值（指标值 / 状态串）
        "triggered": bool,      # 是否触发
        "direction": str|None,  # "加仓" / "减仓" / None
        "weight": float,        # 权重
        "reason": str,          # 触发理由（含指标值），未触发为空串
    }
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from src.signal.models import SignalRule


# ----------------------------------------------------------------------
# 原始指标公式（plan §技术指标公式，纯 pandas）
# ----------------------------------------------------------------------


def ma_cross(nav: pd.Series, short: int = 20, long: int = 60) -> str:
    """MA 均线金叉/死叉检测。

    返回 'golden_cross' / 'death_cross' / 'none'。
    """
    nav = nav.dropna()
    if len(nav) < long + 1:
        return "none"
    ma_short = nav.rolling(short).mean()
    ma_long = nav.rolling(long).mean()
    diff = ma_short - ma_long
    if diff.iloc[-1] > 0 and diff.iloc[-2] <= 0:
        return "golden_cross"
    if diff.iloc[-1] < 0 and diff.iloc[-2] >= 0:
        return "death_cross"
    return "none"


def macd_signal(nav: pd.Series) -> str:
    """MACD 信号：DIF=EMA12-EMA26，DEA=DIF 的 EMA9，histogram=DIF-DEA。

    histogram 由负转正 → buy；由正转负 → sell。返回 'buy' / 'sell' / 'none'。
    """
    nav = nav.dropna()
    if len(nav) < 35:
        return "none"
    ema12 = nav.ewm(span=12, adjust=False).mean()
    ema26 = nav.ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    dea = dif.ewm(span=9, adjust=False).mean()
    histogram = dif - dea
    if histogram.iloc[-1] > 0 and histogram.iloc[-2] <= 0:
        return "buy"
    if histogram.iloc[-1] < 0 and histogram.iloc[-2] >= 0:
        return "sell"
    return "none"


def rsi(nav: pd.Series, period: int = 14) -> float:
    """RSI（SMA 法计算 RS）。返回 0-100，样本不足返回 50（中性）。"""
    nav = nav.dropna()
    if len(nav) < period + 1:
        return 50.0
    diff = nav.diff()
    gain = diff.clip(lower=0).rolling(period).mean()
    loss = (-diff.clip(upper=0)).rolling(period).mean()
    # loss 为 0 时 RS 趋于无穷 → RSI=100
    rs = gain / loss.replace(0, pd.NA)
    rsi_series = 100 - (100 / (1 + rs))
    last = rsi_series.iloc[-1]
    if pd.isna(last):
        # loss=0（全涨）→ 极强；loss 全 0 时 gain 也可能为 0
        return 100.0 if gain.iloc[-1] > 0 else 50.0
    return float(last)


def bollinger(
    nav: pd.Series, window: int = 20, num_std: float = 2.0
) -> tuple[float, float, float]:
    """布林带，返回 (upper, mid, lower)。样本不足时三线收缩到最新价。"""
    nav = nav.dropna()
    if len(nav) < window:
        cur = float(nav.iloc[-1]) if len(nav) else 0.0
        return cur, cur, cur
    mid = nav.rolling(window).mean()
    std = nav.rolling(window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return (
        float(upper.iloc[-1]),
        float(mid.iloc[-1]),
        float(lower.iloc[-1]),
    )


# ----------------------------------------------------------------------
# 规则评估器
# ----------------------------------------------------------------------


def _detail(
    rule: SignalRule,
    value: Any,
    triggered: bool,
    direction: str | None,
    reason: str,
) -> dict:
    return {
        "name": rule.name,
        "category": rule.category,
        "indicator": rule.indicator,
        "value": value,
        "triggered": triggered,
        "direction": direction,
        "weight": rule.weight,
        "reason": reason,
    }


def eval_ma_cross(nav: pd.Series, rule: SignalRule) -> dict:
    """T03：MA 均线金叉/死叉。operator cross_above=金叉加仓，cross_below=死叉减仓。"""
    state = ma_cross(nav)
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "cross_above" and state == "golden_cross":
        triggered, direction = True, "加仓"
        reason = f"【依据：MA金叉={state}】短均线上穿长均线，趋势转强"
    elif rule.operator == "cross_below" and state == "death_cross":
        triggered, direction = True, "减仓"
        reason = f"【依据：MA死叉={state}】短均线下穿长均线，趋势转弱"
    return _detail(rule, state, triggered, direction, reason)


def eval_macd(nav: pd.Series, rule: SignalRule) -> dict:
    """T04：MACD 金叉/死叉。operator cross_above=histogram翻正加仓，cross_below=翻负减仓。"""
    state = macd_signal(nav)
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "cross_above" and state == "buy":
        triggered, direction = True, "加仓"
        reason = f"【依据：MACD柱={state}】DIF 上穿 DEA，动量转正"
    elif rule.operator == "cross_below" and state == "sell":
        triggered, direction = True, "减仓"
        reason = f"【依据：MACD柱={state}】DIF 下穿 DEA，动量转负"
    return _detail(rule, state, triggered, direction, reason)


def eval_rsi(nav: pd.Series, rule: SignalRule) -> dict:
    """T05：RSI 超买超卖。operator below=超卖加仓，above=超买卖出。"""
    val = rsi(nav)
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "below" and val < rule.threshold:
        triggered, direction = True, "加仓"
        reason = f"【依据：RSI={val:.2f} < {rule.threshold}】超卖，反弹概率升高"
    elif rule.operator == "above" and val > rule.threshold:
        triggered, direction = True, "减仓"
        reason = f"【依据：RSI={val:.2f} > {rule.threshold}】超买，回调风险升高"
    return _detail(rule, round(val, 2), triggered, direction, reason)


def eval_bollinger(nav: pd.Series, rule: SignalRule) -> dict:
    """T06：布林带突破。operator below=跌破下轨加仓，above=突破上轨减仓。

    threshold（>0）作为带宽标准差倍数，默认 2.0。
    """
    num_std = rule.threshold if rule.threshold > 0 else 2.0
    upper, mid, lower = bollinger(nav, num_std=num_std)
    cur = float(nav.dropna().iloc[-1]) if len(nav) else 0.0
    value = {"price": round(cur, 4), "upper": round(upper, 4),
             "mid": round(mid, 4), "lower": round(lower, 4)}
    triggered = False
    direction: str | None = None
    reason = ""
    if rule.operator == "below" and cur < lower:
        triggered, direction = True, "加仓"
        reason = f"【依据：价格={cur:.4f} < 布林下轨={lower:.4f}】跌破下轨，超卖"
    elif rule.operator == "above" and cur > upper:
        triggered, direction = True, "减仓"
        reason = f"【依据：价格={cur:.4f} > 布林上轨={upper:.4f}】突破上轨，超买"
    return _detail(rule, value, triggered, direction, reason)
