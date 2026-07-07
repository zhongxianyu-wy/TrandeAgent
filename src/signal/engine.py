"""SignalEngine 抽象接口 + 默认实现（T02 + 组装）。

下游（scheduler / analyzer / arena / CLI）只依赖 SignalEngine 抽象，
具体实现由 DefaultSignalEngine 提供：通过 DataProvider 拉净值，分派到
technical / fundamental / fund_specific 评估器，再由 synthesizer 合成。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Callable

import pandas as pd

from src.data.provider import DataProvider
from src.signal.fund_specific import DEFAULT_INTRADAY_ALERT_THRESHOLD, eval_intraday_alert
from src.signal.fundamental import eval_drawdown, eval_pe_percentile, mock_pe_percentile
from src.signal.models import Signal, SignalRule
from src.signal.synthesizer import synthesize
from src.signal.technical import (
    eval_bollinger,
    eval_macd,
    eval_ma_cross,
    eval_rsi,
)


class SignalEngine(ABC):
    """择时信号引擎抽象（plan §3 接口契约）。

    实现方需保证：
    - calc_signals 返回每只基金一个 Signal（四档之一，附理由）
    - detect_intraday_alert 用于盘中大跌即时推送（不等盘后批量）
    """

    @abstractmethod
    def calc_signals(
        self,
        fund_codes: list[str],
        rules: list[SignalRule],
        end_date: date | None = None,
    ) -> list[Signal]:
        """批量计算择时信号。

        Args:
            fund_codes: 观察池基金代码列表。
            rules: 信号规则列表（来自 config/signals.yaml）。
            end_date: 截止日期，None 表示今天。

        Returns:
            Signal 列表，每只基金一条（净值数据缺失的基金跳过）。
        """

    @abstractmethod
    def detect_intraday_alert(self, fund_code: str, daily_return: float) -> bool:
        """大跌即时检测（AC-2）。

        Args:
            fund_code: 基金代码（保留参数，便于子类按基金类型差异化阈值）。
            daily_return: 单日涨跌幅（百分比，如 -4.0 表示 -4%）。

        Returns:
            True 表示触发大跌警报。
        """


# 估值分位提供者：fund_code → PE 历史分位（0-100）
ValuationProvider = Callable[[str], float]


class DefaultSignalEngine(SignalEngine):
    """默认信号引擎。

    通过 DataProvider 拉取日频净值，按规则 indicator 分派到对应评估器，
    最后由 synthesizer 加权合成为四档 Signal。

    Args:
        provider: 数据访问层（Feature #1）。
        history_days: 回溯净值天数（需足够覆盖 MA60/MACD，默认 200 工作日≈1 年）。
        intraday_threshold: 大跌阈值（百分比，默认 -3.0，全基金类型统一）。
        valuation_provider: 可选的指数估值分位提供者；None 时用 mock_pe_percentile。
    """

    def __init__(
        self,
        provider: DataProvider,
        history_days: int = 400,
        intraday_threshold: float = DEFAULT_INTRADAY_ALERT_THRESHOLD,
        valuation_provider: ValuationProvider | None = None,
    ) -> None:
        self._provider = provider
        self._history_days = history_days
        self._intraday_threshold = intraday_threshold
        self._valuation_provider = valuation_provider

    # ------------------------------------------------------------------
    # SignalEngine 抽象方法实现
    # ------------------------------------------------------------------
    def calc_signals(
        self,
        fund_codes: list[str],
        rules: list[SignalRule],
        end_date: date | None = None,
    ) -> list[Signal]:
        end = end_date or date.today()
        start = end - timedelta(days=self._history_days)
        weights = {r.indicator: r.weight for r in rules}

        results: list[Signal] = []
        for code in fund_codes:
            nav_df = self._provider.get_nav(code, start, end)
            if nav_df is None or nav_df.empty:
                continue
            details = self._evaluate_rules(code, nav_df, rules)
            results.append(
                synthesize(details, weights, fund_code=code, date=end)
            )
        return results

    def detect_intraday_alert(self, fund_code: str, daily_return: float) -> bool:
        del fund_code  # 阈值全基金类型统一，保留参数以匹配接口契约
        return daily_return <= self._intraday_threshold

    # ------------------------------------------------------------------
    # 内部：规则分派
    # ------------------------------------------------------------------
    def _evaluate_rules(
        self, fund_code: str, nav_df: pd.DataFrame, rules: list[SignalRule]
    ) -> list[dict]:
        df = nav_df.sort_values("trade_date").reset_index(drop=True)
        nav = pd.to_numeric(df["unit_nav"], errors="coerce").dropna().reset_index(drop=True)

        details: list[dict] = []
        for rule in rules:
            indicator = rule.indicator
            if indicator == "ma_cross":
                details.append(eval_ma_cross(nav, rule))
            elif indicator == "macd":
                details.append(eval_macd(nav, rule))
            elif indicator == "rsi":
                details.append(eval_rsi(nav, rule))
            elif indicator == "bollinger":
                details.append(eval_bollinger(nav, rule))
            elif indicator == "pe_percentile":
                details.append(self._eval_pe(fund_code, nav, rule))
            elif indicator == "drawdown":
                details.append(eval_drawdown(nav, rule))
            elif indicator == "intraday_alert":
                details.append(eval_intraday_alert(df, rule))
            else:
                details.append(_unknown_rule(rule))
        return details

    def _eval_pe(self, fund_code: str, nav: pd.Series, rule: SignalRule) -> dict:
        if self._valuation_provider is not None:
            try:
                pct = float(self._valuation_provider(fund_code))
            except Exception:  # noqa: BLE001
                pct = mock_pe_percentile(nav)
        else:
            pct = mock_pe_percentile(nav)
        return eval_pe_percentile(rule, pct)


def _unknown_rule(rule: SignalRule) -> dict:
    return {
        "name": rule.name,
        "category": rule.category,
        "indicator": rule.indicator,
        "value": None,
        "triggered": False,
        "direction": None,
        "weight": rule.weight,
        "reason": "",
    }
