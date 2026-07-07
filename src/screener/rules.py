"""5 个运算符实现（T03-T07）。

运算符基于 pandas Series 做批量向量化计算，对整批基金返回布尔掩码。
percentile_top 是相对本批基金的排名百分位筛选（同类百分位）。
"""
from __future__ import annotations

from typing import Callable

import pandas as pd

from src.screener.models import Rule

# 运算符函数签名：(series, value) -> 布尔掩码 Series
OpFunc = Callable[[pd.Series, object], pd.Series]


def resolve_field(df: pd.DataFrame, field: str) -> pd.Series:
    """把点号分隔的字段路径解析为 DataFrame 列。

    同时支持两种写法：
    - 嵌套："l2_performance.sharpe"
    - 扁平："sharpe"（calc_batch 返回的列名）

    优先精确匹配，其次取路径最后一段。
    """
    if field in df.columns:
        return df[field]
    last = field.split(".")[-1]
    if last in df.columns:
        return df[last]
    raise KeyError(
        f"字段 '{field}' 在指标 DataFrame 中找不到（现有列：{list(df.columns)}）"
    )


# ----------------------------------------------------------------------
# T03：>= 运算符
# ----------------------------------------------------------------------
def op_ge(series: pd.Series, value: object) -> pd.Series:
    """大于等于阈值。"""
    return series >= value


# ----------------------------------------------------------------------
# T04：<= 运算符
# ----------------------------------------------------------------------
def op_le(series: pd.Series, value: object) -> pd.Series:
    """小于等于阈值。"""
    return series <= value


# ----------------------------------------------------------------------
# T05：between 运算符
# ----------------------------------------------------------------------
def op_between(series: pd.Series, value: object) -> pd.Series:
    """闭区间 [low, high]。value 需为 [low, high]。"""
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("between 运算符的 value 必须为 [low, high] 列表")
    low, high = value
    return (series >= low) & (series <= high)


# ----------------------------------------------------------------------
# T06：in 运算符
# ----------------------------------------------------------------------
def op_in(series: pd.Series, value: object) -> pd.Series:
    """属于候选集合。value 需为 list。"""
    if not isinstance(value, (list, tuple, set)):
        raise ValueError("in 运算符的 value 必须为列表")
    return series.isin(list(value))


# ----------------------------------------------------------------------
# T07：percentile_top 运算符（同类百分位筛选）
# ----------------------------------------------------------------------
def op_percentile_top(series: pd.Series, value: object) -> pd.Series:
    """排名前 X 比例（值越大越好，取本批 top 分位）。

    value 为比例阈值（0,1），如 0.33 表示保留收益最高的前 1/3。
    阈值 = 本批 (1 - value) 分位数，series >= 阈值即命中。
    """
    fraction = float(value)
    if not 0.0 < fraction < 1.0:
        raise ValueError("percentile_top 的 value 必须在 (0,1) 区间内")
    threshold = series.quantile(1.0 - fraction)
    return series >= threshold


# 运算符注册表
OPERATORS: dict[str, OpFunc] = {
    ">=": op_ge,
    "<=": op_le,
    "between": op_between,
    "in": op_in,
    "percentile_top": op_percentile_top,
}


def apply_rule(rule: Rule, df: pd.DataFrame) -> pd.Series:
    """对整批基金应用单条规则，返回布尔掩码（index 与 df 对齐）。"""
    op_func = OPERATORS.get(rule.op)
    if op_func is None:
        raise ValueError(f"不支持的操作符：{rule.op}")
    series = resolve_field(df, rule.field)
    return op_func(series, rule.value)
