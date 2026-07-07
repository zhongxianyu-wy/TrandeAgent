"""基金服务（薄封装，调业务模块）。

只做协议转换：把 DataFrame / 业务对象 转成 API schema。不重复业务逻辑。
"""
from __future__ import annotations

from datetime import date
from typing import Any, Optional

import pandas as pd

from src.api.schema import (
    BusinessError,
    FundBasicInfo,
    FundListItem,
    NavPoint,
    NotFoundError,
    PaginatedData,
)


def _df_to_fund_basic(row: dict) -> FundBasicInfo:
    return FundBasicInfo(
        fund_code=str(row.get("fund_code", "")),
        fund_name=str(row.get("fund_name", "")),
        fund_type=str(row.get("fund_type", "")),
        fund_category=str(row.get("fund_category", "")),
        manager_names=str(row.get("manager_names", "")),
        establish_date=str(row.get("establish_date", "")),
        latest_scale=row.get("latest_scale"),
        management_fee=row.get("management_fee"),
        custodian_fee=row.get("custodian_fee"),
        history_months=row.get("history_months"),
    )


def list_funds(
    provider: Any,
    *,
    category: Optional[str] = None,
    domain: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    size: int = 20,
    engine: Any = None,
) -> PaginatedData:
    """基金列表（支持大类/搜索过滤 + 分页）。"""
    categories = [category] if category else None
    try:
        df = provider.list_funds(categories=categories)  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise BusinessError("数据提供者不可用") from exc

    if df is None:
        df = pd.DataFrame()
    df = df.copy()
    # 搜索：模糊匹配 fund_code / fund_name / manager_names
    if search:
        mask = pd.Series(False, index=df.index)
        for col in ("fund_code", "fund_name", "manager_names", "pinyin_abbr"):
            if col in df.columns:
                mask |= df[col].astype(str).str.contains(search, case=False, na=False)
        df = df[mask]

    total = int(len(df))
    start = (page - 1) * size
    end = start + size
    page_df = df.iloc[start:end]

    # 评级/近 1 年收益（可选，engine 缺失时留默认）
    rating_map: dict[str, int] = {}
    ret1y_map: dict[str, float] = {}
    if engine is not None and "fund_code" in df.columns:
        try:
            batch = engine.calc_batch(df["fund_code"].astype(str).tolist(), date.today())  # type: ignore[attr-defined]
            if batch is not None and not batch.empty and "fund_code" in batch.columns:
                for _, r in batch.iterrows():
                    code = str(r["fund_code"])
                    rating_map[code] = int(r.get("rating", 0) or 0)
                    ret1y_map[code] = float(r.get("return_1y", 0.0) or 0.0)
        except Exception:  # noqa: BLE001
            pass

    items: list[FundListItem] = []
    for _, row in page_df.iterrows():
        code = str(row.get("fund_code", ""))
        items.append(
            FundListItem(
                fund_code=code,
                fund_name=str(row.get("fund_name", "")),
                fund_category=str(row.get("fund_category", "")),
                fund_type=str(row.get("fund_type", "")),
                latest_scale=row.get("latest_scale"),
                rating=rating_map.get(code, 0),
                return_1y=ret1y_map.get(code),
            )
        )

    return PaginatedData(items=items, page=page, size=size, total=total)


def get_fund_detail(provider: Any, engine: Any, fund_code: str) -> dict:
    """单基金详情（含 L1-L4 指标）。"""
    try:
        basic_df = provider.list_funds()  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise BusinessError("数据提供者不可用") from exc

    basic_row: Optional[dict] = None
    if basic_df is not None and not basic_df.empty:
        match = basic_df[basic_df["fund_code"].astype(str) == fund_code]
        if not match.empty:
            basic_row = match.iloc[0].to_dict()

    if basic_row is None:
        raise NotFoundError(f"基金 {fund_code} 不存在")

    info = _df_to_fund_basic(basic_row)

    indicators = None
    if engine is not None:
        try:
            indicators = engine.calc_all(fund_code, date.today())  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001
            raise BusinessError(f"指标计算失败：{exc}") from exc

    data: dict = info.model_dump()
    if indicators is not None:
        data["indicators"] = indicators.model_dump(mode="json")
    return data


def get_nav(
    provider: Any,
    fund_code: str,
    *,
    start: Optional[date] = None,
    end: Optional[date] = None,
    page: int = 1,
    size: int = 250,
) -> PaginatedData:
    """净值序列（分页，默认 250 天/页）。"""
    try:
        df = provider.get_nav(fund_code, start or date(2000, 1, 1), end or date.today())  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise BusinessError("数据提供者不可用") from exc

    if df is None:
        df = pd.DataFrame()
    df = df.sort_values("trade_date") if not df.empty else df
    total = int(len(df))
    start_i = (page - 1) * size
    page_df = df.iloc[start_i : start_i + size]

    items: list[NavPoint] = []
    for _, row in page_df.iterrows():
        td = row.get("trade_date")
        if hasattr(td, "date"):
            td = td.date()
        elif isinstance(td, str):
            td = pd.to_datetime(td).date()
        items.append(
            NavPoint(
                trade_date=td,
                unit_nav=_safe_float(row.get("unit_nav")),
                accum_nav=_safe_float(row.get("accum_nav")),
                daily_return=_safe_float(row.get("daily_return")),
            )
        )
    return PaginatedData(items=items, page=page, size=size, total=total)


def get_report(analyzer: Any, fund_code: str) -> dict:
    """获取 LLM 分析报告（缓存或实时计算）。"""
    if analyzer is None:
        raise BusinessError("分析器不可用")
    try:
        report = analyzer.analyze(fund_code)  # type: ignore[attr-defined]
    except Exception as exc:  # noqa: BLE001
        raise BusinessError(f"分析失败：{exc}") from exc
    return report.model_dump(mode="json")


def get_holdings(provider: Any, fund_code: str) -> list[dict]:
    """持仓明细。"""
    try:
        df = provider.get_holdings(fund_code)  # type: ignore[attr-defined]
    except AttributeError as exc:
        raise BusinessError("数据提供者不可用") from exc
    if df is None or df.empty:
        return []
    return df.to_dict(orient="records")


def get_cashflow(provider: Any, fund_code: str, engine: Any = None) -> dict:
    """现金流（份额变动/机构持有）。优先用指标引擎的 L4 现金流。"""
    if engine is not None:
        try:
            indicators = engine.calc_all(fund_code, date.today())  # type: ignore[attr-defined]
            l4 = indicators.l4_cashflow
            return {
                "share_change_yoy": l4.share_change_yoy,
                "institution_holding_change": l4.institution_holding_change,
                "dividend_count_5y": l4.dividend_count_5y,
                "institution_holding_pct": indicators.l1_basic.institution_holding_pct,
            }
        except Exception:  # noqa: BLE001
            pass
    # 退化：返回经理表（份额变动无可得数据）
    try:
        mgr = provider.get_manager(fund_code)  # type: ignore[attr-defined]
    except AttributeError:
        mgr = None
    managers = mgr.to_dict(orient="records") if mgr is not None and not mgr.empty else []
    return {"managers": managers}


def _safe_float(v: Any) -> Optional[float]:
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


__all__ = [
    "list_funds",
    "get_fund_detail",
    "get_nav",
    "get_report",
    "get_holdings",
    "get_cashflow",
]
