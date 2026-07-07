"""信号引擎（Feature #7）。

提供择时信号计算：技术面（MA/MACD/RSI/布林）+ 基本面（PE 分位/回撤）
+ 基金专属（大跌警报），加权合成四档信号（加仓/持有/减仓/止损）。

技术指标纯 pandas 实现，不依赖 pandas-ta（plan §1 技术约束）。
"""
from __future__ import annotations

from src.signal.engine import DefaultSignalEngine, SignalEngine
from src.signal.fund_specific import DEFAULT_INTRADAY_ALERT_THRESHOLD
from src.signal.models import Signal, SignalRule
from src.signal.synthesizer import denoise, score_to_level, synthesize

__all__ = [
    "SignalEngine",
    "DefaultSignalEngine",
    "Signal",
    "SignalRule",
    "synthesize",
    "denoise",
    "score_to_level",
    "DEFAULT_INTRADAY_ALERT_THRESHOLD",
]
