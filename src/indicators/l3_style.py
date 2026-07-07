"""L3 风格指标（T06 + T07 + T08）。

- T06：风格九宫格分类（大/中/小盘 × 价值/平衡/成长）
- T07：行业集中度（前 3 大行业占比）+ 持仓换手率
- T08：风格漂移检测（最近 4 季度风格变动频率）
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.indicators.models import L3Style

# 行业 → 价值/成长 倾向（基于申万一级行业特征简化）
_VALUE_INDUSTRIES = {
    "银行", "非银金融", "房地产", "采掘", "公用事业", "交通运输",
    "建筑装饰", "钢铁", "纺织服装",
}
_GROWTH_INDUSTRIES = {
    "电子", "计算机", "通信", "传媒", "医药生物", "电气设备",
    "国防军工", "汽车", "机械设备", "轻工制造",
}

# 大/中/小盘市值分界（亿元），参考 A 股常用阈值
_LARGE_CAP = 500.0
_MID_CAP = 100.0


# ----------------------------------------------------------------------
# T06：风格九宫格分类
# ----------------------------------------------------------------------


def classify_style_box(
    holdings: pd.DataFrame,
    market_caps: dict[str, float] | None = None,
) -> str:
    """根据持仓分类风格九宫格。

    Args:
        holdings: 单期持仓 DataFrame（含 stock_code, holding_pct, industry）。
        market_caps: {stock_code: 市值(亿)} 补充数据；缺失时按集中度倾向默认大盘。

    Returns:
        如 "大盘成长" / "中盘平衡" / "小盘价值" / "未知"。
    """
    if holdings is None or holdings.empty:
        return "未知"

    df = holdings.copy()
    df["holding_pct"] = pd.to_numeric(df["holding_pct"], errors="coerce").fillna(0.0)
    total = df["holding_pct"].sum()
    if total <= 0:
        return "未知"
    weights = df["holding_pct"] / total

    # ---- 盘子大小 ----
    if market_caps:
        caps = np.array(
            [float(market_caps.get(str(c), _LARGE_CAP)) for c in df["stock_code"]],
            dtype=float,
        )
        wcap = float(np.sum(weights.to_numpy() * caps))
        if wcap >= _LARGE_CAP:
            size = "大盘"
        elif wcap >= _MID_CAP:
            size = "中盘"
        else:
            size = "小盘"
    else:
        # 无市值数据：持仓集中度高（top1 > 6%）倾向大盘，否则中盘
        top1 = float(df["holding_pct"].max())
        size = "大盘" if top1 >= 6.0 else "中盘"

    # ---- 价值/成长（行业加权）----
    growth_score = 0.0
    value_score = 0.0
    for _, row in df.iterrows():
        ind = str(row.get("industry", "") or "")
        w = float(row["holding_pct"])
        if ind in _VALUE_INDUSTRIES:
            value_score += w
        elif ind in _GROWTH_INDUSTRIES:
            growth_score += w

    if growth_score > value_score * 1.2:
        style = "成长"
    elif value_score > growth_score * 1.2:
        style = "价值"
    else:
        style = "平衡"

    return f"{size}{style}"


# ----------------------------------------------------------------------
# T07：行业集中度 + 换手率
# ----------------------------------------------------------------------


def calc_industry_concentration_top3(holdings: pd.DataFrame) -> float:
    """前 3 大行业持仓占比之和（[0,1]）。"""
    if holdings is None or holdings.empty:
        return 0.0
    df = holdings.copy()
    df["holding_pct"] = pd.to_numeric(df["holding_pct"], errors="coerce").fillna(0.0)
    total = df["holding_pct"].sum()
    if total <= 0:
        return 0.0
    by_industry = df.groupby("industry")["holding_pct"].sum().sort_values(ascending=False)
    top3 = by_industry.head(3).sum()
    return round(float(top3 / total), 4)


def calc_holding_turnover(holdings: pd.DataFrame) -> float:
    """持仓换手率（年化近似）。

    基于季度持仓快照的变化：对相邻报告期，换手 ≈ Σ|Δw| / 2，
    再乘 4（季频 → 年频）。无多期数据返回 0.0。
    """
    if holdings is None or holdings.empty:
        return 0.0
    df = holdings.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df["holding_pct"] = pd.to_numeric(df["holding_pct"], errors="coerce").fillna(0.0)
    df = df.dropna(subset=["report_date"]).sort_values("report_date")
    dates = sorted(df["report_date"].dt.to_period("Q").unique())
    if len(dates) < 2:
        return 0.0

    # 构造 (period, stock_code) -> holding_pct 透视
    df["period"] = df["report_date"].dt.to_period("Q").astype(str)
    pivot = df.pivot_table(
        index="stock_code", columns="period", values="holding_pct", aggfunc="sum"
    ).fillna(0.0)

    turnovers = []
    for i in range(1, len(dates)):
        prev_col = str(dates[i - 1])
        curr_col = str(dates[i])
        if prev_col not in pivot.columns or curr_col not in pivot.columns:
            continue
        delta = (pivot[curr_col] - pivot[prev_col]).abs().sum()
        # 归一化：除以两期持仓总量的平均
        base = (pivot[prev_col].sum() + pivot[curr_col].sum()) / 2.0
        if base > 0:
            turnovers.append(float(delta) / base)

    if not turnovers:
        return 0.0
    # 平均单期换手 * 4 年化
    annual = float(np.mean(turnovers)) * 4.0
    return round(annual, 4)


# ----------------------------------------------------------------------
# T08：风格漂移检测
# ----------------------------------------------------------------------


def calc_style_drift(
    holdings: pd.DataFrame,
    market_caps: dict[str, float] | None = None,
) -> float:
    """风格漂移得分 [0,1]。

    计算最近 4 个报告期的风格标签序列，漂移得分 = 发生变化的次数 / (期数-1)。
    0 表示完全稳定，1 表示每期都在变。

    Args:
        holdings: 多期持仓 DataFrame（含 report_date）。
        market_caps: 补充市值数据。
    """
    if holdings is None or holdings.empty:
        return 0.0
    df = holdings.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df = df.dropna(subset=["report_date"])
    if df.empty:
        return 0.0
    df["period"] = df["report_date"].dt.to_period("Q")
    # 取最近 4 个报告期
    periods = sorted(df["period"].unique())[-4:]
    if len(periods) < 2:
        return 0.0

    labels = []
    for p in periods:
        sub = df[df["period"] == p]
        labels.append(classify_style_box(sub, market_caps=market_caps))

    changes = sum(1 for i in range(1, len(labels)) if labels[i] != labels[i - 1])
    return round(changes / (len(labels) - 1), 4)


# ----------------------------------------------------------------------
# 组装 L3Style
# ----------------------------------------------------------------------


def calc_l3_style(
    holdings: pd.DataFrame,
    market_caps: dict[str, float] | None = None,
    latest_report_date=None,
) -> L3Style:
    """计算 L3 风格指标。

    Args:
        holdings: 多期持仓 DataFrame（report_date, stock_code, stock_name, holding_pct, industry）。
        market_caps: {stock_code: 市值(亿)} 补充数据。
        latest_report_date: 指定最新报告期用于九宫格；None 自动取最新。
    """
    if holdings is None or holdings.empty:
        return L3Style()

    df = holdings.copy()
    df["report_date"] = pd.to_datetime(df["report_date"], errors="coerce")
    df = df.dropna(subset=["report_date"])

    # 最新一期用于九宫格 + 集中度
    if latest_report_date is not None:
        target = pd.to_datetime(latest_report_date)
        latest = df[df["report_date"] == target]
    else:
        latest_period = df["report_date"].max()
        latest = df[df["report_date"] == latest_period]
    if latest.empty:
        latest = df

    style_box = classify_style_box(latest, market_caps=market_caps)
    concentration = calc_industry_concentration_top3(latest)
    turnover = calc_holding_turnover(df)
    drift = calc_style_drift(df, market_caps=market_caps)

    return L3Style(
        style_box=style_box,
        industry_concentration_top3=concentration,
        holding_turnover=turnover,
        style_drift_score=drift,
    )
