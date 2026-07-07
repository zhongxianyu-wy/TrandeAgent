"""T13: 指标缓存层单元测试。"""
from __future__ import annotations

from datetime import date

import pytest

from src.indicators.cache import IndicatorCache
from src.indicators.models import FundIndicators, L1Basic


@pytest.fixture
def cache(tmp_path):
    c = IndicatorCache(tmp_path / "test_cache.db")
    yield c
    c.close()


@pytest.fixture
def sample_indicators():
    return FundIndicators(
        fund_code="000001",
        as_of_date=date(2026, 7, 4),
        l1_basic=L1Basic(scale=27.3),
        rating=4,
    )


class TestIndicatorCache:
    def test_miss_returns_none(self, cache):
        assert cache.get("000001", date(2026, 7, 4)) is None

    def test_set_then_get(self, cache, sample_indicators):
        cache.set(sample_indicators)
        got = cache.get("000001", date(2026, 7, 4))
        assert got is not None
        assert got.fund_code == "000001"
        assert got.rating == 4
        assert got.l1_basic.scale == pytest.approx(27.3)

    def test_overwrite(self, cache, sample_indicators):
        cache.set(sample_indicators)
        updated = sample_indicators.model_copy(update={"rating": 5})
        cache.set(updated)
        got = cache.get("000001", date(2026, 7, 4))
        assert got.rating == 5

    def test_invalidate_single(self, cache, sample_indicators):
        cache.set(sample_indicators)
        assert cache.invalidate("000001") >= 1
        assert cache.get("000001", date(2026, 7, 4)) is None

    def test_invalidate_all(self, cache, sample_indicators):
        cache.set(sample_indicators)
        cache.set(sample_indicators.model_copy(update={"fund_code": "000002"}))
        assert cache.invalidate() >= 2
        assert cache.get("000001", date(2026, 7, 4)) is None

    def test_different_date_miss(self, cache, sample_indicators):
        cache.set(sample_indicators)
        assert cache.get("000001", date(2026, 7, 5)) is None

    def test_context_manager(self, tmp_path, sample_indicators):
        with IndicatorCache(tmp_path / "cm.db") as c:
            c.set(sample_indicators.model_copy(update={"fund_code": "x"}))
        # 退出后连接已关闭，不报错即通过

    def test_corrupt_json_returns_none(self, cache):
        # 直接写入损坏 JSON
        with cache._lock:
            cache._conn.execute(
                "INSERT INTO indicator_cache (fund_code, as_of_date, layer, indicators) "
                "VALUES (?, ?, ?, ?)",
                ("000099", "2026-07-04", "full", "{bad json"),
            )
        assert cache.get("000099", date(2026, 7, 4)) is None
