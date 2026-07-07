"""T09/T10: AkShareProvider 单元测试（mock akshare）。

通过 monkeypatch 替换 `src.data.akshare_provider.ak` 的相关函数，
验证分类映射、字段转换、缓存命中、失败降级逻辑。
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.data.akshare_provider import AkShareProvider
from src.data.config import DataConfig
from src.data.retry import UpstreamUnavailable


def _make_provider(tmp_config: DataConfig) -> AkShareProvider:
    """构造一个 RateLimiter 几乎不阻塞的 provider（加快测试）。"""
    tmp_config.rate_limit.min_interval_seconds = 0.0
    tmp_config.retry.backoff_base = 0.001
    p = AkShareProvider(tmp_config)
    return p


@pytest.fixture
def provider(tmp_config: DataConfig):
    p = _make_provider(tmp_config)
    yield p
    p.close()


class TestListFunds:
    def test_list_funds_classifies_and_caches(
        self, provider: AkShareProvider, mock_fund_name_df, monkeypatch
    ):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em",
            lambda: mock_fund_name_df,
        )
        df = provider.list_funds()
        # 11 行中：3 active + 2 etf_link + 1 index + 2 qdii = 8，剔除 债/货/FOF 3 行
        assert len(df) == 8
        cats = set(df["fund_category"])
        assert cats == {"active_stock", "index", "etf_link", "qdii"}

    def test_list_funds_category_filter(self, provider: AkShareProvider, mock_fund_name_df, monkeypatch):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em", lambda: mock_fund_name_df
        )
        df = provider.list_funds(categories=["index"])
        assert len(df) >= 1
        assert (df["fund_category"] == "index").all()

    def test_list_funds_cache_hit_no_network(
        self, provider: AkShareProvider, mock_fund_name_df, monkeypatch
    ):
        call_count = {"n": 0}

        def _spy():
            call_count["n"] += 1
            return mock_fund_name_df

        monkeypatch.setattr("src.data.akshare_provider.ak.fund_name_em", _spy)
        # 第一次：走上游
        provider.list_funds()
        assert call_count["n"] == 1
        # 第二次：缓存命中（当日已更新），不再调上游
        provider.list_funds()
        assert call_count["n"] == 1

    def test_list_funds_excludes_debt_and_money(
        self, provider: AkShareProvider, mock_fund_name_df, monkeypatch
    ):
        """AC-4: 列表不含债基/货基。"""
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em", lambda: mock_fund_name_df
        )
        df = provider.list_funds()
        names = df["fund_name"].tolist()
        assert not any("债" in n for n in names)
        assert not any("货" in n for n in names)


class TestGetNav:
    def test_get_nav_merges_unit_and_accum(
        self,
        provider: AkShareProvider,
        mock_unit_nav_df,
        mock_accum_nav_df,
        monkeypatch,
    ):
        def _fake_em(symbol, indicator, **kwargs):
            if indicator == "单位净值走势":
                return mock_unit_nav_df
            if indicator == "累计净值走势":
                return mock_accum_nav_df
            return pd.DataFrame()

        monkeypatch.setattr("src.data.akshare_provider.ak.fund_open_fund_info_em", _fake_em)
        df = provider.get_nav("000001", date(2026, 6, 1), date(2026, 7, 4))
        assert len(df) == 4
        assert "unit_nav" in df.columns
        assert "accum_nav" in df.columns
        assert "daily_return" in df.columns
        # 累计净值已合并
        assert df["accum_nav"].notna().all()

    def test_get_nav_cache_hit(
        self, provider: AkShareProvider, mock_unit_nav_df, mock_accum_nav_df, monkeypatch
    ):
        calls = {"n": 0}

        def _spy(symbol, indicator, **kwargs):
            calls["n"] += 1
            return mock_unit_nav_df if indicator == "单位净值走势" else mock_accum_nav_df

        monkeypatch.setattr("src.data.akshare_provider.ak.fund_open_fund_info_em", _spy)
        provider.get_nav("000001", date(2026, 6, 1), date(2026, 7, 4))
        first = calls["n"]
        # 第二次命中缓存
        provider.get_nav("000001", date(2026, 6, 1), date(2026, 7, 4))
        assert calls["n"] == first  # 不再调上游


class TestGetManager:
    def test_get_manager_filters_by_code(
        self, provider: AkShareProvider, mock_manager_df, monkeypatch
    ):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_manager_em", lambda: mock_manager_df
        )
        df = provider.get_manager("000001")
        assert len(df) == 1
        assert df.iloc[0]["manager_name"] == "王泽实"
        # tenure_years = 3650 / 365
        assert df.iloc[0]["tenure_years"] == pytest.approx(10.0, rel=0.01)


class TestGetHoldings:
    def test_get_holdings_parses(
        self, provider: AkShareProvider, mock_holdings_df, monkeypatch
    ):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_portfolio_hold_em",
            lambda symbol, date: mock_holdings_df,
        )
        df = provider.get_holdings("000001")
        assert len(df) == 3
        assert "report_date" in df.columns
        # report_date 解析自 "2024年1季度股票投资明细"
        dates = pd.to_datetime(df["report_date"]).dt.date.unique()
        assert date(2024, 3, 31) in dates
        assert date(2024, 6, 30) in dates


class TestFailureDegradation:
    def test_get_nav_degrades_to_empty_on_failure(
        self, provider: AkShareProvider, monkeypatch
    ):
        """AC-3: 上游失败，重试耗尽后降级（空缓存返空 DataFrame）。"""

        def _always_fail(*args, **kwargs):
            raise RuntimeError("network down")

        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_open_fund_info_em", _always_fail
        )
        df = provider.get_nav("000001", date(2026, 1, 1), date(2026, 7, 4))
        assert df.empty  # 降级返回缓存（空）
        # 新鲜度报告标记失败
        rep = provider.get_freshness_report()
        failed = rep[rep["source"] == "failed"]
        assert len(failed) >= 1

    def test_list_funds_degrades_to_cache(
        self, provider: AkShareProvider, mock_fund_name_df, monkeypatch
    ):
        """AC-3: list_funds 首次成功写缓存，第二次上游挂掉时降级到缓存。"""
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em", lambda: mock_fund_name_df
        )
        provider.list_funds()  # 首次成功

        # 清掉"今日已更新"标记，强制第二次走降级路径
        provider._meta.upsert_freshness("ALL", "fund_basic", "2020-01-01", True, "cache")

        def _fail():
            raise RuntimeError("down")

        monkeypatch.setattr("src.data.akshare_provider.ak.fund_name_em", _fail)
        df = provider.list_funds()  # 应降级到缓存
        assert not df.empty
