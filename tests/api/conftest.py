"""pytest fixtures：mock 全部业务模块 + TestClient（T14）。

策略：用 dependency_overrides 把 deps.py 的工厂全部替换为 mock，
保证测试不依赖真实网络/数据库。后台任务在测试中同步执行（BackgroundTasks
会在响应返回后执行，TestClient 会等待其完成）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import deps
from src.api.app import create_app
from src.api.services.job_service import JobStore
from src.api.services.strategy_service import ArenaStore, ObservationStore


# ---------------------------------------------------------------------------
# 业务模块 mock 工厂
# ---------------------------------------------------------------------------
def make_fund_basic_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "fund_code": "000001",
                "fund_name": "华夏成长",
                "fund_type": "混合型",
                "fund_category": "active_stock",
                "manager_names": "张三",
                "establish_date": "2001-12-18",
                "latest_scale": 35.2,
                "management_fee": 0.015,
                "custodian_fee": 0.0025,
                "history_months": 280,
            },
            {
                "fund_code": "161725",
                "fund_name": "招商沪深300ETF联接",
                "fund_type": "指数型",
                "fund_category": "etf_link",
                "manager_names": "李四",
                "establish_date": "2017-07-12",
                "latest_scale": 120.0,
                "management_fee": 0.005,
                "custodian_fee": 0.001,
                "history_months": 100,
            },
        ]
    )


def make_nav_df(code: str = "000001") -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-01", periods=30)
    nav = [1.0 + i * 0.001 for i in range(30)]
    return pd.DataFrame(
        {
            "trade_date": dates.date,
            "unit_nav": nav,
            "accum_nav": nav,
            "daily_return": [0.001] * 30,
            "is_adjusted": [True] * 30,
        }
    )


def make_holdings_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "report_date": "2025-12-31",
                "stock_code": "600519",
                "stock_name": "贵州茅台",
                "holding_pct": 8.5,
                "industry": "食品饮料",
            }
        ]
    )


def make_manager_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "manager_name": "张三",
                "fund_code": "000001",
                "start_date": "2018-01-01",
                "end_date": None,
                "tenure_years": 8.0,
                "total_assets": 100.0,
            }
        ]
    )


def make_freshness_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"fund_code": "000001", "field_name": "nav", "is_stale": 0},
            {"fund_code": "161725", "field_name": "nav", "is_stale": 1},
        ]
    )


def make_fund_indicators(code: str = "000001"):
    from src.indicators.models import FundIndicators, L2Performance

    return FundIndicators(
        fund_code=code,
        as_of_date=date.today(),
        l2_performance=L2Performance(
            return_1y=0.15,
            return_3y=0.40,
            return_5y=0.80,
            sharpe=1.2,
            max_drawdown=-0.18,
            volatility=0.15,
        ),
        rating=4,
    )


def make_batch_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"fund_code": "000001", "rating": 4, "return_1y": 0.15},
            {"fund_code": "161725", "rating": 3, "return_1y": 0.08},
        ]
    )


def make_fund_report(code: str = "000001"):
    from src.analyzer.models import FundReport, ReportSection

    return FundReport(
        fund_code=code,
        one_liner="质量较高，建议关注",
        label="建议",
        sections=[ReportSection(title="业绩归因", content="近1年收益 15%。")],
        recommendation_pool=True,
    )


def make_arena_run_result():
    from src.arena.models import (
        ArenaRanking,
        ArenaRunResult,
        BacktestResult,
        Strategy,
    )

    s1 = Strategy(
        strategy_id="strat_001",
        prototype_id="proto_4433",
        domain="成长",
        params={"n": 4433},
        source_explanation="4433 法则",
    )
    s2 = Strategy(
        strategy_id="strat_002",
        prototype_id="proto_4433",
        domain="价值",
        params={"n": 4433},
        source_explanation="价值变体",
    )
    results = [
        BacktestResult(
            strategy_id="strat_001",
            annual_return=0.20,
            sharpe=1.3,
            max_drawdown=-0.15,
            win_rate=0.55,
            calmar=1.3,
            backtest_years=5,
            precise=True,
        ),
        BacktestResult(
            strategy_id="strat_002",
            annual_return=0.12,
            sharpe=0.9,
            max_drawdown=-0.20,
            win_rate=0.50,
            calmar=0.6,
            backtest_years=5,
            precise=True,
        ),
    ]
    rankings = [
        ArenaRanking(strategy_id="strat_001", domain="成长", composite_score=0.9, rank_in_domain=1),
        ArenaRanking(strategy_id="strat_002", domain="价值", composite_score=0.7, rank_in_domain=1),
    ]
    return ArenaRunResult(
        strategies=[s1, s2],
        fast_results=results,
        precise_results=results,
        rankings=rankings,
    )


def make_app_config(pool=None):
    from src.config_manager.schema import AppConfig

    return AppConfig(observation_pool=list(pool or ["000001"]))


# ---------------------------------------------------------------------------
# mock fixtures
# ---------------------------------------------------------------------------
@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.list_funds.return_value = make_fund_basic_df()
    provider.get_nav.return_value = make_nav_df()
    provider.get_holdings.return_value = make_holdings_df()
    provider.get_manager.return_value = make_manager_df()
    provider.get_freshness_report.return_value = make_freshness_df()
    provider.refresh_incremental.return_value = {"updated": 2}
    return provider


@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.calc_all.return_value = make_fund_indicators()
    engine.calc_batch.return_value = make_batch_df()
    return engine


@pytest.fixture
def mock_analyzer():
    analyzer = MagicMock()
    analyzer.analyze.return_value = make_fund_report()
    return analyzer


@pytest.fixture
def mock_signal_engine():
    from src.signal.models import Signal

    engine = MagicMock()
    engine.calc_signals.return_value = [
        Signal(
            fund_code="000001",
            date=date.today(),
            level="持有",
            reasons=["MA 金叉"],
            score=0.3,
        )
    ]
    return engine


@pytest.fixture
def mock_config_manager():
    mgr = MagicMock()
    mgr.load.return_value = make_app_config()
    mgr.save_with_commit.return_value = "deadbeef"
    mgr.analyze_impact.return_value = []
    mgr.log.return_value = [{"hash": "deadbeef", "date": "2026-07-07", "message": "init"}]
    mgr.rollback.return_value = make_app_config()
    return mgr


@pytest.fixture
def mock_arena_pipeline():
    pipe = MagicMock()
    pipe.run.return_value = make_arena_run_result()
    return pipe


@pytest.fixture
def mock_feishu_writer():
    writer = MagicMock()
    writer.add_to_pool.return_value = True
    writer.remove_from_pool.return_value = True
    return writer


@pytest.fixture
def in_memory_job_store():
    return JobStore()  # 无 db_path → 纯内存


@pytest.fixture
def arena_store_with_data():
    store = ArenaStore()
    store.load_result(make_arena_run_result())
    return store


# ---------------------------------------------------------------------------
# TestClient（全部依赖注入覆盖为 mock）
# ---------------------------------------------------------------------------
@pytest.fixture
def app(
    mock_provider,
    mock_engine,
    mock_analyzer,
    mock_signal_engine,
    mock_config_manager,
    mock_arena_pipeline,
    mock_feishu_writer,
):
    application = create_app()
    overrides = {
        deps.get_data_provider: lambda: mock_provider,
        deps.get_indicator_engine: lambda: mock_engine,
        deps.get_screener: lambda: MagicMock(),
        deps.get_analyzer: lambda: mock_analyzer,
        deps.get_signal_engine: lambda: mock_signal_engine,
        deps.get_arena_pipeline: lambda: mock_arena_pipeline,
        deps.get_config_manager: lambda: mock_config_manager,
        deps.get_feishu_writer: lambda: mock_feishu_writer,
    }
    for dep, fn in overrides.items():
        application.dependency_overrides[dep] = fn
    yield application
    application.dependency_overrides.clear()


@pytest.fixture
def client(app, in_memory_job_store, arena_store_with_data):
    # 覆盖运行态依赖
    app.dependency_overrides[deps.get_job_store] = lambda: in_memory_job_store
    app.dependency_overrides[deps.get_arena_store] = lambda: arena_store_with_data
    app.dependency_overrides[deps.get_observation_store] = lambda: ObservationStore()
    # raise_server_exceptions=False 以便断言 500 响应（ServerErrorMiddleware 会重抛 Exception）
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


# 提供工厂给需要自定义数据的测试
@pytest.fixture
def factories():
    return {
        "fund_basic_df": make_fund_basic_df,
        "nav_df": make_nav_df,
        "fund_indicators": make_fund_indicators,
        "fund_report": make_fund_report,
        "arena_run_result": make_arena_run_result,
        "app_config": make_app_config,
    }
