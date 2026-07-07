"""L1 基本面指标（T03）。

从 list_funds 与 get_manager 的原始数据中提取规模、年限、任期、费率等。
机构持有比例不在 DataProvider 标准接口内，作为可选补充参数传入。
"""
from __future__ import annotations

from datetime import date

import pandas as pd

from src.indicators.models import L1Basic


def _safe_float(value, default: float = 0.0) -> float:
    """安全转 float，NaN/None 返回默认值。"""
    if value is None:
        return default
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(f):
        return default
    return f


def calc_establish_years(establish_date, as_of_date: date) -> float:
    """由成立日期计算年限。"""
    if establish_date is None or (isinstance(establish_date, float) and pd.isna(establish_date)):
        return 0.0
    try:
        ed = pd.to_datetime(establish_date).date()
    except (ValueError, TypeError):
        return 0.0
    return round((as_of_date - ed).days / 365.25, 2)


def calc_l1_basic(
    fund_info: pd.Series | dict,
    managers: pd.DataFrame,
    as_of_date: date,
    institution_holding_pct: float | None = None,
) -> L1Basic:
    """计算 L1 基本面指标。

    Args:
        fund_info: list_funds 返回的单行（Series 或 dict）。
        managers: get_manager 返回的 DataFrame。
        as_of_date: 截止日期。
        institution_holding_pct: 机构持有比例（DataProvider 不提供，可选补充）。

    Returns:
        L1Basic。
    """
    def _get(key, default=None):
        if isinstance(fund_info, pd.Series):
            return fund_info.get(key, default)
        return fund_info.get(key, default)

    scale = _safe_float(_get("latest_scale"))
    establish_years = calc_establish_years(_get("establish_date"), as_of_date)
    management_fee = _safe_float(_get("management_fee"))
    custodian_fee = _safe_float(_get("custodian_fee"))

    # 现任经理任期：取 end_date 为空或仍在职（end_date >= as_of_date）的经理
    manager_tenure = 0.0
    if managers is not None and not managers.empty:
        tenures = pd.to_numeric(managers["tenure_years"], errors="coerce")
        tenures = tenures.dropna()
        if not tenures.empty:
            # 优先取任期最长者（通常为现任主理人）
            manager_tenure = float(tenures.max())

    inst_pct = _safe_float(institution_holding_pct) if institution_holding_pct is not None else 0.0
    # 限制在 [0, 1]
    inst_pct = max(0.0, min(1.0, inst_pct))

    return L1Basic(
        scale=round(scale, 4),
        establish_years=establish_years,
        manager_tenure_years=round(manager_tenure, 4),
        institution_holding_pct=round(inst_pct, 4),
        management_fee=round(management_fee, 6),
        custodian_fee=round(custodian_fee, 6),
    )
