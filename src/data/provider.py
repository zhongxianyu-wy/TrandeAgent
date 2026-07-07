"""数据访问层抽象接口（plan §3.1）。

下游所有业务模块只依赖 `DataProvider`，不依赖具体实现（AkShareProvider 等），
以此隔离上游数据源变更风险（ADR-001）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Literal

import pandas as pd

# 基金大类（context.md 边界：仅这 4 类，不含债基/货基/FOF/REITs）
FundCategory = Literal["qdii", "index", "etf_link", "active_stock"]


class DataProvider(ABC):
    """数据访问层抽象。

    实现方需保证：
    - 缓存命中时不发起网络请求（FR-4）
    - 上游失败重试 3 次后降级到缓存，标记 is_stale（FR-6）
    - 每次拉取更新新鲜度报告（FR-7）
    """

    @abstractmethod
    def list_funds(self, categories: list[FundCategory] | None = None) -> pd.DataFrame:
        """列出基金基本信息。

        Args:
            categories: 大类过滤；None 表示全部已支持的 4 类（不含债基/货基）。

        Returns:
            DataFrame 列：fund_code, fund_name, fund_type, fund_category,
            manager_names, establish_date, latest_scale, management_fee,
            custodian_fee, history_months
        """

    @abstractmethod
    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        """获取日频净值序列。

        Returns:
            DataFrame 列：trade_date, unit_nav, accum_nav, daily_return, is_adjusted
            按 trade_date 升序。
        """

    @abstractmethod
    def get_manager(self, fund_code: str) -> pd.DataFrame:
        """获取基金历任经理信息。

        Returns:
            DataFrame 列：manager_name, fund_code, start_date, end_date,
            tenure_years, total_assets
        """

    @abstractmethod
    def get_holdings(
        self, fund_code: str, report_date: date | None = None
    ) -> pd.DataFrame:
        """获取季度持仓。

        Args:
            report_date: 指定季报日期；None 表示所有可得季报。

        Returns:
            DataFrame 列：report_date, stock_code, stock_name, holding_pct, industry
        """

    @abstractmethod
    def refresh_incremental(self, fund_codes: list[str] | None = None) -> dict:
        """增量更新（每日盘后调用）。

        Args:
            fund_codes: 指定基金；None 表示全市场。

        Returns:
            新鲜度报告 dict，结构见 spec §8.3。
        """

    @abstractmethod
    def refresh_full_backfill(self, fund_codes: list[str], years: int = 5) -> dict:
        """首次全量回填（手动触发 / 异步后台）。

        Returns:
            新鲜度报告 dict。
        """

    @abstractmethod
    def get_freshness_report(self) -> pd.DataFrame:
        """查询新鲜度报告。

        Returns:
            DataFrame 列：fund_code, field_name, last_update, is_stale, source, fail_reason
        """
