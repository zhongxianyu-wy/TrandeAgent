"""15 个策略原型的 Python 信号生成实现（T08）。

每个类继承 :class:`StrategyBase`，依据基金净值序列生成持仓信号。
信号语义在单基金回测下统一为"持有该基金(1) / 空仓(0)"。

原型清单（与 ``config/strategy_prototypes.yaml`` 一一对应）：
1. Strategy4433               4433法则（多周期排名代理）
2. StrategyDualMomentum       双动量
3. StrategyGrid               网格交易
4. StrategyDCA                定投
5. StrategyMACross            均线择时
6. StrategyMACD               MACD趋势
7. StrategyRSIReversal        RSI反转
8. StrategyBollingerBreakout  布林带突破
9. StrategyDrawdownRecovery   最大回撤修复
10. StrategyPEDCA             估值定投
11. StrategyMomentumRotation  动量轮动
12. StrategyLowVol            低波动
13. StrategyTurtle            趋势跟踪（海龟简化）
14. StrategyMeanReversion     均值回归
15. StrategyRiskParity        风险平价（简化）
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.arena.strategies.base import StrategyBase


def _ffill_signal(raw: pd.Series, fill: float = 0.0) -> pd.Series:
    """将"事件触发"型原始信号前向填充为持仓状态。"""
    return raw.reindex(raw.index).ffill().fillna(fill).astype(float)


# 1. 4433 法则 -------------------------------------------------------------
class Strategy4433(StrategyBase):
    prototype_id = "proto_4433"
    default_params = {"short_window": 63, "mid_window": 126, "long_window": 252}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        m3 = nav.pct_change(int(params.get("short_window", 63)))
        m6 = nav.pct_change(int(params.get("mid_window", 126)))
        m12 = nav.pct_change(int(params.get("long_window", 252)))
        return ((m3 > 0) & (m6 > 0) & (m12 > 0)).astype(float)


# 2. 双动量 ----------------------------------------------------------------
class StrategyDualMomentum(StrategyBase):
    prototype_id = "proto_dual_momentum"
    default_params = {"lookback_months": 12, "abs_window": 252, "rel_window": 63}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        abs_window = int(params.get("abs_window", 252))
        rel_window = int(params.get("rel_window", 63))
        abs_mom = nav.pct_change(abs_window) > 0
        rel_mom = nav.pct_change(rel_window) > 0
        return (abs_mom & rel_mom).astype(float)


# 3. 网格交易 --------------------------------------------------------------
class StrategyGrid(StrategyBase):
    prototype_id = "proto_grid"
    default_params = {"window": 60}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        window = int(params.get("window", 60))
        lo = nav.rolling(window).min()
        hi = nav.rolling(window).max()
        mid = (lo + hi) / 2
        # 处于区间下半区（便宜）时持有
        return (nav < mid).astype(float)


# 4. 定投 ------------------------------------------------------------------
class StrategyDCA(StrategyBase):
    prototype_id = "proto_dca"
    default_params = {}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        return pd.Series(1.0, index=nav.index)


# 5. 均线择时 --------------------------------------------------------------
class StrategyMACross(StrategyBase):
    prototype_id = "proto_ma_cross"
    default_params = {"fast": 20, "slow": 60}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        fast = int(params.get("fast", 20))
        slow = int(params.get("slow", 60))
        ma_f = nav.rolling(fast).mean()
        ma_s = nav.rolling(slow).mean()
        return (ma_f > ma_s).astype(float)


# 6. MACD 趋势 -------------------------------------------------------------
class StrategyMACD(StrategyBase):
    prototype_id = "proto_macd"
    default_params = {"fast": 12, "slow": 26, "signal": 9}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        fast = int(params.get("fast", 12))
        slow = int(params.get("slow", 26))
        signal = int(params.get("signal", 9))
        ema_f = nav.ewm(span=fast, adjust=False).mean()
        ema_s = nav.ewm(span=slow, adjust=False).mean()
        dif = ema_f - ema_s
        dea = dif.ewm(span=signal, adjust=False).mean()
        return (dif > dea).astype(float)


# 7. RSI 反转 --------------------------------------------------------------
class StrategyRSIReversal(StrategyBase):
    prototype_id = "proto_rsi_reversal"
    default_params = {"period": 14, "oversold": 30, "overbought": 70}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        period = int(params.get("period", 14))
        oversold = float(params.get("oversold", 30))
        overbought = float(params.get("overbought", 70))
        delta = nav.diff()
        gain = delta.clip(lower=0.0).rolling(period).mean()
        loss = (-delta.clip(upper=0.0)).rolling(period).mean()
        rs = gain / loss.replace(0.0, np.nan)
        rsi = 100.0 - 100.0 / (1.0 + rs)
        raw = pd.Series(np.nan, index=nav.index, dtype=float)
        raw[rsi < oversold] = 1.0
        raw[rsi > overbought] = 0.0
        return _ffill_signal(raw, fill=0.0)


# 8. 布林带突破 ------------------------------------------------------------
class StrategyBollingerBreakout(StrategyBase):
    prototype_id = "proto_bollinger_breakout"
    default_params = {"window": 20, "k": 2.0}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        window = int(params.get("window", 20))
        k = float(params.get("k", 2.0))
        ma = nav.rolling(window).mean()
        sd = nav.rolling(window).std()
        upper = ma + k * sd
        lower = ma - k * sd
        raw = pd.Series(np.nan, index=nav.index, dtype=float)
        raw[nav > upper] = 1.0
        raw[nav < lower] = 0.0
        return _ffill_signal(raw, fill=0.0)


# 9. 最大回撤修复 ----------------------------------------------------------
class StrategyDrawdownRecovery(StrategyBase):
    prototype_id = "proto_drawdown_recovery"
    default_params = {"threshold": 0.15}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        threshold = float(params.get("threshold", 0.15))
        peak = nav.cummax()
        drawdown = (nav - peak) / peak
        # 回撤未击穿阈值时持有，击穿时避险空仓
        return (drawdown > -threshold).astype(float)


# 10. 估值定投 -------------------------------------------------------------
class StrategyPEDCA(StrategyBase):
    prototype_id = "proto_pe_dca"
    default_params = {"window": 252, "high_pct": 0.8, "low_pct": 0.3}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        window = int(params.get("window", 252))
        high_pct = float(params.get("high_pct", 0.8))
        low_pct = float(params.get("low_pct", 0.3))
        rank = nav.rolling(window).rank(pct=True)
        raw = pd.Series(1.0, index=nav.index, dtype=float)
        raw[rank > high_pct] = 0.0  # 高估空仓
        raw[rank <= low_pct] = 1.0  # 低估满仓
        return _ffill_signal(raw, fill=1.0)


# 11. 动量轮动 -------------------------------------------------------------
class StrategyMomentumRotation(StrategyBase):
    prototype_id = "proto_momentum_rotation"
    default_params = {"window": 60}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        window = int(params.get("window", 60))
        mom = nav.pct_change(window)
        return (mom > 0).astype(float)


# 12. 低波动 ---------------------------------------------------------------
class StrategyLowVol(StrategyBase):
    prototype_id = "proto_low_vol"
    default_params = {}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        return pd.Series(1.0, index=nav.index)


# 13. 趋势跟踪（海龟简化）-------------------------------------------------
class StrategyTurtle(StrategyBase):
    prototype_id = "proto_turtle"
    default_params = {"breakout_days": 20, "exit_days": 10}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        n = int(params.get("breakout_days", 20))
        exit_n = int(params.get("exit_days", 10))
        high = nav.rolling(n).max()
        low = nav.rolling(exit_n).min()
        raw = pd.Series(np.nan, index=nav.index, dtype=float)
        raw[nav >= high.shift(1)] = 1.0
        raw[nav <= low.shift(1)] = 0.0
        return _ffill_signal(raw, fill=0.0)


# 14. 均值回归 -------------------------------------------------------------
class StrategyMeanReversion(StrategyBase):
    prototype_id = "proto_mean_reversion"
    default_params = {"window": 30, "threshold": 1.0}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        window = int(params.get("window", 30))
        k = float(params.get("threshold", 1.0))
        ma = nav.rolling(window).mean()
        sd = nav.rolling(window).std()
        lower = ma - k * sd
        upper = ma + k * sd
        raw = pd.Series(np.nan, index=nav.index, dtype=float)
        raw[nav < lower] = 1.0
        raw[nav > upper] = 0.0
        return _ffill_signal(raw, fill=0.0)


# 15. 风险平价（简化）-----------------------------------------------------
class StrategyRiskParity(StrategyBase):
    prototype_id = "proto_risk_parity"
    default_params = {}

    def generate_signals(self, nav: pd.Series, params: dict) -> pd.Series:
        return pd.Series(1.0, index=nav.index)


# ---- 原型注册表：prototype_id -> 类 ----
PROTOTYPE_REGISTRY: dict[str, type[StrategyBase]] = {
    cls.prototype_id: cls
    for cls in (
        Strategy4433,
        StrategyDualMomentum,
        StrategyGrid,
        StrategyDCA,
        StrategyMACross,
        StrategyMACD,
        StrategyRSIReversal,
        StrategyBollingerBreakout,
        StrategyDrawdownRecovery,
        StrategyPEDCA,
        StrategyMomentumRotation,
        StrategyLowVol,
        StrategyTurtle,
        StrategyMeanReversion,
        StrategyRiskParity,
    )
}


def get_strategy_class(prototype_id: str) -> type[StrategyBase]:
    """按 prototype_id 取原型类；未知 id 抛 KeyError（防幻觉）。"""
    if prototype_id not in PROTOTYPE_REGISTRY:
        raise KeyError(f"未知策略原型：{prototype_id}（不在 15 个原型注册表中）")
    return PROTOTYPE_REGISTRY[prototype_id]


def list_prototype_ids() -> list[str]:
    return list(PROTOTYPE_REGISTRY.keys())
