"""周期分析计算测试（T11）。"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.api.services.period_service import (
    compute_nav_curve,
    compute_period_return,
)


def _make_nav_df(days=260):
    dates = pd.bdate_range("2025-01-01", periods=days)
    nav = [1.0 * (1.001 ** i) for i in range(days)]
    return pd.DataFrame({"trade_date": dates, "unit_nav": nav})


def test_compute_period_return_monthly():
    df = _make_nav_df(260)
    pr = compute_period_return(df, period="monthly")
    assert pr.period == "monthly"
    assert len(pr.labels) >= 1
    assert len(pr.returns) == len(pr.labels)


def test_compute_period_return_with_benchmark():
    df = _make_nav_df(260)
    bench = _make_nav_df(260)
    pr = compute_period_return(df, period="monthly", benchmark_df=bench)
    assert len(pr.benchmark_returns) == len(pr.returns)


def test_compute_period_return_weekly():
    df = _make_nav_df(60)
    pr = compute_period_return(df, period="weekly")
    assert len(pr.labels) >= 1


def test_compute_period_return_quarterly():
    df = _make_nav_df(260)
    pr = compute_period_return(df, period="quarterly")
    assert any("Q" in lbl for lbl in pr.labels)


def test_compute_period_return_yearly():
    df = _make_nav_df(520)
    pr = compute_period_return(df, period="yearly")
    assert len(pr.labels) >= 1


def test_compute_period_return_daily():
    df = _make_nav_df(10)
    pr = compute_period_return(df, period="daily")
    assert len(pr.labels) == 9  # 首日无收益率


def test_compute_period_return_invalid_period_defaults_monthly():
    df = _make_nav_df(60)
    pr = compute_period_return(df, period="hourly")
    assert pr.period == "monthly"


def test_compute_period_return_empty_df():
    pr = compute_period_return(pd.DataFrame(), period="monthly")
    assert pr.returns == []
    assert pr.labels == []


def test_compute_period_return_benchmark_shorter():
    """基准序列短于主序列时补 0 对齐。"""
    df = _make_nav_df(120)
    bench = _make_nav_df(20)
    pr = compute_period_return(df, period="monthly", benchmark_df=bench)
    assert len(pr.benchmark_returns) == len(pr.returns)


def test_compute_nav_curve():
    df = _make_nav_df(30)
    nc = compute_nav_curve(df)
    assert len(nc.nav) == 30
    assert len(nc.drawdown) == 30
    # 回撤全为非正
    assert all(d <= 1e-9 for d in nc.drawdown)


def test_compute_nav_curve_with_benchmark():
    df = _make_nav_df(30)
    bench = _make_nav_df(30)
    nc = compute_nav_curve(df, benchmark_df=bench)
    assert len(nc.benchmark_nav) == 30


def test_compute_nav_curve_empty():
    nc = compute_nav_curve(pd.DataFrame())
    assert nc.nav == []


def test_compute_nav_curve_accum_nav_fallback():
    """无 unit_nav 时退化为 accum_nav。"""
    df = _make_nav_df(20).rename(columns={"unit_nav": "accum_nav"})
    nc = compute_nav_curve(df)
    assert len(nc.nav) == 20


def test_compute_period_return_benchmark_longer_truncated():
    df = _make_nav_df(60)
    bench = _make_nav_df(400)
    pr = compute_period_return(df, period="monthly", benchmark_df=bench)
    assert len(pr.benchmark_returns) == len(pr.returns)
