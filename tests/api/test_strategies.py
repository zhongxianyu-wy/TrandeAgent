"""strategies 路由测试（T05，FR-2）。"""
from __future__ import annotations

import pandas as pd

from src.api import deps
from src.api.services import strategy_service
from src.api.services.strategy_service import ArenaStore
from src.api.schema import BusinessError, NotFoundError
from tests.api.conftest import make_arena_run_result


def test_list_strategies(client):
    r = client.get("/api/strategies")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 2


def test_list_strategies_domain_filter(client):
    r = client.get("/api/strategies?domain=成长")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["domain"] == "成长"


def test_list_strategies_sort(client):
    r = client.get("/api/strategies?sort=return")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert items[0]["annual_return"] >= items[-1]["annual_return"]


def test_get_strategy_detail(client):
    r = client.get("/api/strategies/strat_001")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["strategy_id"] == "strat_001"
    assert data["backtest"]["annual_return"] == 0.20


def test_get_strategy_not_found(client):
    r = client.get("/api/strategies/nope")
    assert r.status_code == 404


def test_get_strategy_timeseries_empty_nav(client):
    r = client.get("/api/strategies/strat_001/timeseries?period=monthly")
    assert r.status_code == 200
    # 无 nav_series → 空序列
    data = r.json()["data"]
    assert data["period"] == "monthly"


def test_get_strategy_timeseries_with_nav(arena_store_with_data):
    """注入 nav 序列后能算出周期收益。"""
    import pandas as pd

    dates = pd.bdate_range("2025-01-01", periods=120)
    nav = [1.0 + i * 0.002 for i in range(120)]
    arena_store_with_data.nav_series["strat_001"] = pd.DataFrame(
        {"trade_date": dates, "unit_nav": nav}
    )
    pr = strategy_service.get_strategy_timeseries(
        arena_store_with_data, "strat_001", "monthly"
    )
    assert pr.period == "monthly"
    assert len(pr.labels) >= 1


def test_get_strategy_nav_curve(client):
    r = client.get("/api/strategies/strat_001/nav")
    assert r.status_code == 200
    # 无 nav_series → 空 NavCurve
    assert r.json()["data"]["nav"] == []


def test_get_strategy_cashflow(client):
    r = client.get("/api/strategies/strat_001/cashflow")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["dates"] == []


def test_adopt_strategy(client):
    r = client.post("/api/strategies/strat_001/adopt")
    assert r.status_code == 200
    assert r.json()["data"]["adopted"] is True
    # 详情中反映 adopted
    r2 = client.get("/api/strategies/strat_001")
    assert r2.json()["data"]["adopted"] is True


def test_adopt_disabled_strategy_raises():
    store = ArenaStore()
    store.load_result(make_arena_run_result())
    store.disabled.add("strat_001")
    try:
        strategy_service.adopt_strategy(store, "strat_001")
        assert False
    except BusinessError:
        pass


def test_disable_strategy(client):
    r = client.post("/api/strategies/strat_001/disable")
    assert r.status_code == 200
    assert r.json()["data"]["disabled"] is True


def test_adopt_not_found(client):
    r = client.post("/api/strategies/nope/adopt")
    assert r.status_code == 404


def test_regenerate_async(client):
    r = client.post("/api/strategies/regenerate?count=10")
    assert r.status_code == 200
    job_id = r.json()["data"]["job_id"]
    r2 = client.get(f"/api/jobs/{job_id}")
    assert r2.status_code == 200
    assert r2.json()["data"]["status"] == "succeeded"
