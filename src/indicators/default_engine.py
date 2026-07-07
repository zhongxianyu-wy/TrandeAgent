"""默认指标引擎实现（T12 + 组装）。

组装 L1-L4 计算层 + 评级 + 缓存，提供 calc_all / calc_batch / get_rating。
批量计算用 concurrent.futures 并行。
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, timedelta

import numpy as np
import pandas as pd
from loguru import logger

from src.data.provider import DataProvider
from src.indicators.cache import IndicatorCache
from src.indicators.engine import IndicatorEngine
from src.indicators.l1_basic import calc_l1_basic
from src.indicators.l2_performance import calc_l2_performance
from src.indicators.l3_style import calc_l3_style
from src.indicators.l4_cashflow import calc_l4_cashflow
from src.indicators.models import FundIndicators
from src.indicators.rating import calc_rating


@dataclass
class SupplementaryData:
    """单只基金的补充数据（DataProvider 标准接口不覆盖的部分）。

    缺失字段保持默认值，对应指标按 0 处理。
    """

    market_caps: dict[str, float] | None = None
    institution_current: float | None = None
    institution_prev: float | None = None
    shares_series: pd.Series | dict | None = None
    dividends: pd.DataFrame | list | None = None
    extra: dict = field(default_factory=dict)


class DefaultIndicatorEngine(IndicatorEngine):
    """默认指标计算引擎。

    通过 DataProvider 拉取原始数据，分四层计算指标并评级。
    支持可选缓存（同日命中直接返回）与批量并行。
    """

    def __init__(
        self,
        provider: DataProvider,
        cache: IndicatorCache | None = None,
        rf_annual: float = 0.02,
        benchmark_returns: np.ndarray | pd.Series | None = None,
        max_workers: int | None = None,
    ) -> None:
        self._provider = provider
        self._cache = cache
        self._rf_annual = rf_annual
        self._benchmark_returns = (
            np.asarray(benchmark_returns, dtype=float)
            if benchmark_returns is not None
            else None
        )
        self._max_workers = max_workers

    # ------------------------------------------------------------------
    # 可覆盖的补充数据钩子
    # ------------------------------------------------------------------
    def _get_supplementary(self, fund_code: str) -> SupplementaryData:
        """子类可覆盖以提供市值/机构持有/份额/分红等补充数据。"""
        return SupplementaryData()

    # ------------------------------------------------------------------
    # calc_all
    # ------------------------------------------------------------------
    def calc_all(
        self, fund_code: str, end: date, years: int = 5
    ) -> FundIndicators:
        # 缓存命中
        if self._cache is not None:
            cached = self._cache.get(fund_code, end)
            if cached is not None:
                logger.debug("指标缓存命中 {} @ {}", fund_code, end)
                return cached

        indicators = self._compute_one(fund_code, end, years, peer_returns=None)
        indicators.rating = self.get_rating(indicators)

        if self._cache is not None:
            self._cache.set(indicators)
        return indicators

    # ------------------------------------------------------------------
    # calc_batch（并行 + 同类排名百分位）
    # ------------------------------------------------------------------
    def calc_batch(
        self, fund_codes: list[str], end: date, years: int = 5
    ) -> pd.DataFrame:
        if not fund_codes:
            return pd.DataFrame()

        workers = self._max_workers or min(8, max(1, len(fund_codes)))
        results: dict[str, FundIndicators] = {}

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {
                pool.submit(self._compute_one, code, end, years, None): code
                for code in fund_codes
            }
            for fut in as_completed(future_map):
                code = future_map[fut]
                try:
                    results[code] = fut.result()
                except Exception as e:  # noqa: BLE001
                    logger.warning("calc_batch 计算失败 {}: {}", code, e)

        # 同类排名百分位：用本批基金的 1 年收益互为 peer
        peer_returns = np.array(
            [r.l2_performance.return_1y for r in results.values()], dtype=float
        )
        for ind in results.values():
            # 百分位 = 比本基金收益更高的同类占比（越小越靠前）
            better = float(
                np.sum(peer_returns > ind.l2_performance.return_1y)
            )
            ind.l2_performance.rank_1y_percentile = round(
                better / max(len(peer_returns), 1), 4
            )
            ind.rating = self.get_rating(ind)
            if self._cache is not None:
                self._cache.set(ind)

        rows = [self._indicators_to_row(results[c], end) for c in fund_codes if c in results]
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # get_rating
    # ------------------------------------------------------------------
    def get_rating(self, indicators: FundIndicators) -> int:
        return calc_rating(indicators)

    # ------------------------------------------------------------------
    # 内部：单基金全层计算
    # ------------------------------------------------------------------
    def _compute_one(
        self,
        fund_code: str,
        end: date,
        years: int,
        peer_returns,
    ) -> FundIndicators:
        start = end - timedelta(days=365 * years)
        sup = self._get_supplementary(fund_code)

        # 原始数据
        funds_df = self._provider.list_funds()
        if not funds_df.empty:
            match = funds_df[funds_df["fund_code"].astype(str) == fund_code]
            fund_info = match.iloc[0].to_dict() if not match.empty else {}
        else:
            fund_info = {}
        managers = self._provider.get_manager(fund_code)
        nav_df = self._provider.get_nav(fund_code, start, end)
        holdings = self._provider.get_holdings(fund_code)

        # L1
        l1 = calc_l1_basic(
            fund_info,
            managers,
            end,
            institution_holding_pct=sup.institution_current,
        )
        # L2
        l2 = calc_l2_performance(
            nav_df,
            end,
            benchmark_returns=self._benchmark_returns,
            peer_returns=peer_returns,
            rf_annual=self._rf_annual,
        )
        # L3
        l3 = calc_l3_style(holdings, market_caps=sup.market_caps)
        # L4
        l4 = calc_l4_cashflow(
            shares_series=sup.shares_series,
            institution_current=sup.institution_current,
            institution_prev=sup.institution_prev,
            dividends=sup.dividends,
            as_of_date=end,
        )

        return FundIndicators(
            fund_code=fund_code,
            as_of_date=end,
            l1_basic=l1,
            l2_performance=l2,
            l3_style=l3,
            l4_cashflow=l4,
        )

    @staticmethod
    def _indicators_to_row(ind: FundIndicators, as_of: date) -> dict:
        """把 FundIndicators 拍平为 DataFrame 一行。"""
        return {
            "fund_code": ind.fund_code,
            "as_of_date": as_of,
            "rating": ind.rating,
            "scale": ind.l1_basic.scale,
            "establish_years": ind.l1_basic.establish_years,
            "manager_tenure_years": ind.l1_basic.manager_tenure_years,
            "institution_holding_pct": ind.l1_basic.institution_holding_pct,
            "management_fee": ind.l1_basic.management_fee,
            "return_1y": ind.l2_performance.return_1y,
            "return_3y": ind.l2_performance.return_3y,
            "return_5y": ind.l2_performance.return_5y,
            "rank_1y_percentile": ind.l2_performance.rank_1y_percentile,
            "max_drawdown": ind.l2_performance.max_drawdown,
            "sharpe": ind.l2_performance.sharpe,
            "volatility": ind.l2_performance.volatility,
            "alpha": ind.l2_performance.alpha,
            "beta": ind.l2_performance.beta,
            "style_box": ind.l3_style.style_box,
            "industry_concentration_top3": ind.l3_style.industry_concentration_top3,
            "holding_turnover": ind.l3_style.holding_turnover,
            "style_drift_score": ind.l3_style.style_drift_score,
            "share_change_yoy": ind.l4_cashflow.share_change_yoy,
            "institution_holding_change": ind.l4_cashflow.institution_holding_change,
            "dividend_count_5y": ind.l4_cashflow.dividend_count_5y,
        }
