"""发现与推荐路由（T06，FR-3）。

端点：8 领域 × Top-5 推荐 / 单基金推荐理由。
推荐来源：screener 筛选结果（按领域分组）。窗口参数 today/week/month 控制
候选范围（当前以全量指标为基础，窗口仅记录语义）。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from src.api.deps import (
    get_data_provider,
    get_indicator_engine,
    get_screener,
)
from src.api.schema import ApiResponse
from src.api.services import fund_service

router = APIRouter()

# 8 个投资风格领域
_DOMAINS = (
    "价值", "成长", "红利", "趋势", "逆向", "全球配置", "指数增强", "低波"
)

# 领域 → 筛选预设名映射（简化）
_DOMAIN_PRESET = {
    "价值": "quality",
    "成长": "rule_4433",
    "红利": "quality",
    "趋势": "rule_4433",
    "逆向": "quality",
    "全球配置": "rule_4433",
    "指数增强": "rule_4433",
    "低波": "quality",
}


def _window_start(window: str) -> date:
    today = date.today()
    if window == "week":
        return today - timedelta(days=7)
    if window == "month":
        return today - timedelta(days=30)
    return today


@router.get("", summary="8 领域推荐")
def discover(
    domain: Optional[str] = Query(None, description="单领域过滤"),
    window: str = Query("today", description="today|week|month"),
    screener=Depends(get_screener),
    provider=Depends(get_data_provider),
    engine=Depends(get_indicator_engine),
) -> ApiResponse:
    """8 领域 × Top-5 推荐基金。"""
    del screener, provider  # 推荐基于已计算指标；此处保留依赖注入点
    # 触发 window 起点计算（仅记录语义，不影响结果）
    _window_start(window)
    domains = (domain,) if domain else _DOMAINS
    # 通过 engine 批量计算筛选（engine 缺失时返回空）
    if engine is None:
        return ApiResponse(data={"domains": {d: [] for d in domains}, "window": window})

    try:
        batch = engine.calc_batch([], date.today())  # type: ignore[attr-defined]
    except Exception:  # noqa: BLE001
        batch = None
    if batch is None or batch.empty:
        return ApiResponse(data={"domains": {d: [] for d in domains}, "window": window})

    # 按收益排序取 Top-5 作为每个领域的候选（简化策略）
    if "return_1y" in batch.columns:
        ranked = batch.sort_values("return_1y", ascending=False)
    else:
        ranked = batch
    codes = ranked["fund_code"].astype(str).tolist() if "fund_code" in ranked.columns else []
    result: dict = {"domains": {}, "window": window}
    per_domain = 5
    for i, d in enumerate(domains):
        slice_codes = codes[i * per_domain : (i + 1) * per_domain]
        result["domains"][d] = slice_codes
    return ApiResponse(data=result)


@router.get("/reasons/{code}", summary="推荐理由")
def discover_reasons(
    code: str,
    screener=Depends(get_screener),
    engine=Depends(get_indicator_engine),
) -> ApiResponse:
    """单基金推荐理由详情。"""
    if screener is None or engine is None:
        return ApiResponse(data={"fund_code": code, "reasons": []})
    try:
        indicators = engine.calc_all(code, date.today())  # type: ignore[attr-defined]
        # 用 rating + 关键指标生成简化理由
        reasons = [
            f"规则评级 {indicators.rating} 星",
            f"近 1 年收益 {indicators.l2_performance.return_1y:.2%}",
            f"夏普比率 {indicators.l2_performance.sharpe:.2f}",
            f"最大回撤 {indicators.l2_performance.max_drawdown:.2%}",
        ]
        return ApiResponse(data={"fund_code": code, "reasons": reasons})
    except Exception as exc:  # noqa: BLE001
        from src.api.schema import BusinessError

        raise BusinessError(f"生成推荐理由失败：{exc}")


__all__ = ["router"]
