"""T06/T07: SQLite (MetaDB) + Parquet (ParquetStore) 缓存层测试。"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from src.data.cache import MetaDB, ParquetStore


class TestMetaDB:
    def test_fund_basic_upsert_and_get(self, meta_db: MetaDB):
        row = {
            "fund_code": "000001",
            "fund_name": "华夏成长混合",
            "fund_type": "混合型-偏股",
            "fund_category": "active_stock",
            "manager_names": "王泽实",
            "latest_scale": 27.3,
        }
        meta_db.upsert_fund_basic(row)
        df = meta_db.get_fund_basic()
        assert len(df) == 1
        assert df.iloc[0]["fund_code"] == "000001"
        assert df.iloc[0]["fund_category"] == "active_stock"

    def test_fund_basic_upsert_idempotent(self, meta_db: MetaDB):
        row = {"fund_code": "000001", "fund_name": "A", "fund_type": "t", "fund_category": "index"}
        meta_db.upsert_fund_basic(row)
        row2 = {"fund_code": "000001", "fund_name": "A2", "fund_type": "t", "fund_category": "index"}
        meta_db.upsert_fund_basic(row2)
        df = meta_db.get_fund_basic()
        assert len(df) == 1
        assert df.iloc[0]["fund_name"] == "A2"  # 更新生效

    def test_fund_basic_category_filter(self, meta_db: MetaDB):
        for code, cat in [("000001", "active_stock"), ("161725", "index"), ("000834", "qdii")]:
            meta_db.upsert_fund_basic(
                {"fund_code": code, "fund_name": "x", "fund_type": "t", "fund_category": cat}
            )
        df = meta_db.get_fund_basic(categories=["index"])
        assert len(df) == 1
        assert df.iloc[0]["fund_code"] == "161725"

    def test_manager_upsert_replace(self, meta_db: MetaDB):
        meta_db.upsert_fund_basic(
            {"fund_code": "000001", "fund_name": "x", "fund_type": "t", "fund_category": "active_stock"}
        )
        meta_db.upsert_managers(
            "000001", [{"manager_name": "张三", "tenure_years": 5.0, "total_assets": 10.0}]
        )
        df = meta_db.get_managers("000001")
        assert len(df) == 1
        assert df.iloc[0]["manager_name"] == "张三"
        # 替换
        meta_db.upsert_managers(
            "000001",
            [
                {"manager_name": "李四", "tenure_years": 3.0, "total_assets": 8.0},
                {"manager_name": "王五", "tenure_years": 2.0, "total_assets": 5.0},
            ],
        )
        df = meta_db.get_managers("000001")
        assert len(df) == 2  # 先删后插

    def test_freshness_upsert(self, meta_db: MetaDB):
        meta_db.upsert_freshness("000001", "nav", "2026-07-04", False, "fresh")
        df = meta_db.get_freshness()
        assert len(df) == 1
        assert df.iloc[0]["source"] == "fresh"
        # update on conflict
        meta_db.upsert_freshness("000001", "nav", "2026-07-04", True, "failed", "timeout")
        df = meta_db.get_freshness()
        assert len(df) == 1
        assert df.iloc[0]["source"] == "failed"
        assert df.iloc[0]["is_stale"] == 1

    def test_freshness_filter_by_stale(self, meta_db: MetaDB):
        meta_db.upsert_freshness("000001", "nav", "2026-07-04", False, "fresh")
        meta_db.upsert_freshness("000002", "nav", None, True, "failed", "down")
        stale = meta_db.get_freshness(is_stale=True)
        assert len(stale) == 1
        assert stale.iloc[0]["fund_code"] == "000002"


class TestParquetStore:
    def _sample_nav(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "trade_date": [date(2026, 7, 1), date(2026, 7, 2), date(2026, 7, 3)],
                "unit_nav": [1.1, 1.11, 1.12],
                "accum_nav": [2.1, 2.11, 2.12],
                "daily_return": [0.5, 0.9, 0.9],
                "is_adjusted": [True, True, True],
            }
        )

    def test_nav_write_read_roundtrip(self, parquet_store: ParquetStore):
        df = self._sample_nav()
        n = parquet_store.write_nav("000001", df)
        assert n == 3
        got = parquet_store.read_nav("000001")
        assert len(got) == 3
        assert list(got["unit_nav"]) == [1.1, 1.11, 1.12]

    def test_nav_write_dedup(self, parquet_store: ParquetStore):
        df1 = self._sample_nav()
        parquet_store.write_nav("000001", df1)
        # 重复日期 + 新日期
        df2 = pd.DataFrame(
            {
                "trade_date": [date(2026, 7, 3), date(2026, 7, 4)],
                "unit_nav": [1.99, 1.13],  # 7-3 被覆盖
                "accum_nav": [2.99, 2.13],
                "daily_return": [0.0, 0.1],
                "is_adjusted": [True, True],
            }
        )
        n = parquet_store.write_nav("000001", df2)
        assert n == 4  # 3 原有 + 1 新
        got = parquet_store.read_nav("000001")
        assert len(got) == 4
        july3 = got[pd.to_datetime(got["trade_date"]).dt.date == date(2026, 7, 3)]
        assert july3.iloc[0]["unit_nav"] == 1.99  # keep=last

    def test_nav_date_range_filter(self, parquet_store: ParquetStore):
        parquet_store.write_nav("000001", self._sample_nav())
        got = parquet_store.read_nav("000001", start=date(2026, 7, 2), end=date(2026, 7, 2))
        assert len(got) == 1

    def test_nav_last_date(self, parquet_store: ParquetStore):
        parquet_store.write_nav("000001", self._sample_nav())
        assert parquet_store.nav_last_date("000001") == date(2026, 7, 3)
        assert parquet_store.nav_last_date("999999") is None

    def test_read_nav_empty(self, parquet_store: ParquetStore):
        got = parquet_store.read_nav("NOPE")
        assert got.empty
        assert "trade_date" in got.columns

    def test_holdings_write_read(self, parquet_store: ParquetStore):
        df = pd.DataFrame(
            {
                "report_date": [date(2024, 3, 31), date(2024, 6, 30)],
                "stock_code": ["002025", "600862"],
                "stock_name": ["航天电器", "中航高科"],
                "holding_pct": [3.46, 3.24],
                "industry": [None, None],
            }
        )
        parquet_store.write_holdings("000001", df)
        got = parquet_store.read_holdings("000001")
        assert len(got) == 2

    def test_holdings_filter_by_report_date(self, parquet_store: ParquetStore):
        df = pd.DataFrame(
            {
                "report_date": [date(2024, 3, 31), date(2024, 6, 30)],
                "stock_code": ["A", "B"],
                "stock_name": ["a", "b"],
                "holding_pct": [1.0, 2.0],
                "industry": [None, None],
            }
        )
        parquet_store.write_holdings("000001", df)
        got = parquet_store.read_holdings("000001", report_date=date(2024, 6, 30))
        assert len(got) == 1
        assert got.iloc[0]["stock_code"] == "B"

    def test_has_any_nav(self, parquet_store: ParquetStore):
        assert parquet_store.has_any_nav() is False
        parquet_store.write_nav("000001", self._sample_nav())
        assert parquet_store.has_any_nav() is True
