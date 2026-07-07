"""T15: 集成测试 - 验收标准 AC-1 ~ AC-5。

用 mock 上游跑通"全量→增量→查询→失败降级→幂等"全流程。
性能基准（AC-1/AC-2 耗时）因 mock 无法真正验证，改为验证逻辑正确性。
真实烟雾测试见 scripts/smoke_test_data.py（手动）。
"""
from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import pytest

from src.data.akshare_provider import AkShareProvider
from src.data.config import DataConfig


@pytest.fixture
def provider(tmp_config: DataConfig):
    tmp_config.rate_limit.min_interval_seconds = 0.0
    tmp_config.retry.backoff_base = 0.001
    p = AkShareProvider(tmp_config)
    yield p
    p.close()


def _install_nav_mock(monkeypatch, unit_df, accum_df, calls=None):
    def _spy(symbol, indicator, **kwargs):
        if calls is not None:
            calls.append((symbol, indicator))
        return unit_df if indicator == "单位净值走势" else accum_df

    monkeypatch.setattr("src.data.akshare_provider.ak.fund_open_fund_info_em", _spy)


class TestAC2Incremental:
    """AC-2: 增量更新，仅拉新增，缓存命中。"""

    def test_incremental_only_fetches_new(self, provider: AkShareProvider, monkeypatch):
        today = date.today()
        old_dates = [today - timedelta(days=d) for d in (5, 4, 3)]

        # 1) 手动写缓存模拟"已有历史"（避免真实网络）
        from src.data.cache import ParquetStore

        pq = ParquetStore(provider._config.cache_path)
        nav_df = pd.DataFrame(
            {
                "trade_date": old_dates,
                "unit_nav": [1.1, 1.11, 1.12],
                "accum_nav": [2.1, 2.11, 2.12],
                "daily_return": [0.1, 0.2, 0.3],
                "is_adjusted": [True, True, True],
            }
        )
        pq.write_nav("000001", nav_df)
        assert pq.nav_last_date("000001") == old_dates[-1]

        # 2) mock 上游返回旧 + 新日期
        full_unit = pd.DataFrame(
            {
                "净值日期": [d.isoformat() for d in old_dates] + [today.isoformat()],
                "单位净值": [1.1, 1.11, 1.12, 1.13],
                "日增长率": [0.1, 0.2, 0.3, 0.4],
            }
        )
        full_accum = pd.DataFrame(
            {
                "净值日期": full_unit["净值日期"],
                "累计净值": [2.1, 2.11, 2.12, 2.13],
            }
        )
        calls: list = []
        _install_nav_mock(monkeypatch, full_unit, full_accum, calls=calls)

        # 3) 增量：只写新日期
        provider.refresh_incremental(["000001"])

        # 4) 验证缓存包含全部 4 天（旧 3 + 新 1），不重复
        got = provider._pq.read_nav("000001")
        assert len(got) == 4


class TestAC3FailureDegradation:
    """AC-3: 上游挂掉 → 重试 3 次 → 降级缓存，不崩溃。"""

    def test_retry_then_degrade(self, provider: AkShareProvider, monkeypatch):
        attempts = {"n": 0}

        def _flaky(*args, **kwargs):
            attempts["n"] += 1
            raise RuntimeError("upstream down")

        monkeypatch.setattr("src.data.akshare_provider.ak.fund_open_fund_info_em", _flaky)
        # 不崩溃
        df = provider.get_nav("000001", date(2026, 1, 1), date(2026, 7, 4))
        assert df.empty
        # 重试了 3 次
        assert attempts["n"] == 3
        # 新鲜度标记失败
        rep = provider.get_freshness_report()
        assert (rep["source"] == "failed").any()


class TestAC4CategoryFilter:
    """AC-4: 返回列表有 fund_category，可过滤。"""

    def test_filter_returns_only_requested(
        self, provider: AkShareProvider, mock_fund_name_df, monkeypatch
    ):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em", lambda: mock_fund_name_df
        )
        for cat in ["active_stock", "index", "qdii", "etf_link"]:
            df = provider.list_funds(categories=[cat])
            assert (df["fund_category"] == cat).all()


class TestAC5Idempotent:
    """AC-5: 同一天重复运行幂等，不重复写已有数据。"""

    def test_repeat_run_no_duplicate(self, provider: AkShareProvider, monkeypatch):
        unit = pd.DataFrame(
            {
                "净值日期": ["2026-07-01", "2026-07-02"],
                "单位净值": [1.1, 1.11],
                "日增长率": [0.1, 0.2],
            }
        )
        accum = pd.DataFrame(
            {"净值日期": ["2026-07-01", "2026-07-02"], "累计净值": [2.1, 2.11]}
        )
        _install_nav_mock(monkeypatch, unit, accum)

        provider.refresh_full_backfill(["000001"], years=5)
        n1 = len(provider._pq.read_nav("000001"))
        # 第二次跑同样的数据
        provider.refresh_full_backfill(["000001"], years=5)
        n2 = len(provider._pq.read_nav("000001"))
        assert n1 == n2  # 幂等，不翻倍


class TestEndToEndWorkflow:
    """全流程：list → nav → manager → holdings → freshness。"""

    def test_full_workflow(
        self,
        provider: AkShareProvider,
        mock_fund_name_df,
        mock_unit_nav_df,
        mock_accum_nav_df,
        mock_holdings_df,
        mock_manager_df,
        monkeypatch,
    ):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_name_em", lambda: mock_fund_name_df
        )
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_open_fund_info_em",
            lambda symbol, indicator, **kw: mock_unit_nav_df
            if indicator == "单位净值走势"
            else mock_accum_nav_df,
        )
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_portfolio_hold_em",
            lambda symbol, date: mock_holdings_df,
        )
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_manager_em", lambda: mock_manager_df
        )

        funds = provider.list_funds()
        assert len(funds) > 0

        nav = provider.get_nav("000001", date(2026, 6, 1), date(2026, 7, 4))
        assert len(nav) == 4

        mgr = provider.get_manager("000001")
        assert len(mgr) == 1

        hold = provider.get_holdings("000001")
        assert len(hold) == 3

        rep = provider.get_freshness_report()
        assert len(rep) > 0


class TestSampleFallback:
    """Clarify Q6: 空缓存返回样例。"""

    def test_get_sample_nav(self, provider: AkShareProvider, mock_unit_nav_df, mock_accum_nav_df, monkeypatch):
        monkeypatch.setattr(
            "src.data.akshare_provider.ak.fund_open_fund_info_em",
            lambda symbol, indicator, **kw: mock_unit_nav_df
            if indicator == "单位净值走势"
            else mock_accum_nav_df,
        )
        samples = provider.get_sample_nav()
        assert len(samples) == 5  # SAMPLE_FUND_CODES
        # 每只都有数据（mock 不会失败）
        for code, df in samples.items():
            assert len(df) > 0
