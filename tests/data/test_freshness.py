"""T08: FreshnessReport 单元测试。"""
from __future__ import annotations

from datetime import date

import pytest

from src.data.cache import MetaDB
from src.data.freshness import FreshnessReport


@pytest.fixture
def report(meta_db: MetaDB) -> FreshnessReport:
    return FreshnessReport(meta_db)


class TestFreshnessReport:
    def test_record_fresh(self, report: FreshnessReport):
        report.record_fresh("000001", "nav", "2026-07-04")
        df = report.get_report()
        assert len(df) == 1
        r = df.iloc[0]
        assert r["source"] == "fresh"
        assert r["is_stale"] == 0

    def test_record_cache_hit(self, report: FreshnessReport):
        report.record_cache_hit("000001", "nav", "2026-07-04")
        df = report.get_report()
        assert df.iloc[0]["source"] == "cache"

    def test_record_failure(self, report: FreshnessReport):
        report.record_failure("000001", "nav", "timeout", last_update="2026-07-01")
        df = report.get_report()
        r = df.iloc[0]
        assert r["source"] == "failed"
        assert r["is_stale"] == 1
        assert r["fail_reason"] == "timeout"

    def test_filter_by_stale(self, report: FreshnessReport):
        report.record_fresh("A", "nav", "2026-07-04")
        report.record_failure("B", "nav", "down")
        stale = report.get_report(is_stale=True)
        assert len(stale) == 1
        assert stale.iloc[0]["fund_code"] == "B"

    def test_summary_empty(self, report: FreshnessReport):
        s = report.summary()
        assert s["total_records"] == 0

    def test_summary_with_data(self, report: FreshnessReport):
        report.record_fresh("A", "nav", "2026-07-04")
        report.record_cache_hit("A", "manager", "2026-06-30")
        report.record_failure("B", "nav", "timeout")
        s = report.summary()
        assert s["total_records"] == 3
        assert s["stale_count"] == 1
        assert s["failed_count"] == 1
        assert s["by_source"]["fresh"] == 1
        assert s["by_source"]["cache"] == 1
        assert s["by_source"]["failed"] == 1
        assert s["by_field"]["nav"] == 2
