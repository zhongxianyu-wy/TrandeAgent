"""策略竞技场 Pydantic 数据模型（T01）。

对应 plan §2 数据模型。Strategy / BacktestResult / ForwardResult / ArenaRanking
四个核心对象，承载"生成→回测→纸上模拟→排名"全流程。
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _utcnow() -> datetime:
    """timezone-aware UTC 当前时间（避免 utcnow() 弃用告警）。"""
    return datetime.now(timezone.utc)

# 8 个投资风格领域（spec §FR-4）
Domain = Literal[
    "价值", "成长", "红利", "趋势", "逆向", "全球配置", "指数增强", "低波"
]
DOMAINS: tuple[str, ...] = (
    "价值", "成长", "红利", "趋势", "逆向", "全球配置", "指数增强", "低波"
)


class Strategy(BaseModel):
    """单个策略实例，可追溯到"原型 + 大师（可选）+ 参数组合"。"""

    strategy_id: str  # "strat_001"
    prototype_id: str  # "proto_4433"，必须命中已知原型
    mind_model_id: str | None = None  # "mind_buffett"，可选
    domain: Domain
    params: dict = Field(default_factory=dict)  # 参数组合
    source_explanation: str = ""  # 可追溯说明（防幻觉）
    created_at: datetime = Field(default_factory=_utcnow)

    # 差异维度矩阵（T04）的 5 个轴，用于去重与可追溯
    timing_logic: str | None = None  # 择时逻辑：技术面/基本面/技术+基本/无择时
    rebalance_freq: str | None = None  # 调仓频率：周/双周/月/季
    risk_threshold: float | None = None  # 风控止损阈值（0.05~0.20）
    concentration: str | None = None  # 持仓集中度：Top5/Top10/Top20/Top50

    @field_validator("prototype_id")
    @classmethod
    def _prototype_nonempty(cls, v: str) -> str:
        if not v or not v.startswith("proto_"):
            raise ValueError(f"prototype_id 必须以 proto_ 开头，得到：{v}")
        return v


class BacktestResult(BaseModel):
    """历史回测结果。max_drawdown 规定为非正数（<=0）。"""

    strategy_id: str
    annual_return: float
    sharpe: float
    max_drawdown: float  # <= 0
    win_rate: float
    calmar: float
    backtest_years: int
    precise: bool = False  # True=含手续费/滑点的精细回测


class ForwardResult(BaseModel):
    """纸上模拟结果。is_qualified 表示是否满 30 个交易日。"""

    strategy_id: str
    forward_days: int
    forward_return: float
    daily_returns: list[float] = Field(default_factory=list)
    is_qualified: bool = False  # forward_days >= 30


class ArenaRanking(BaseModel):
    """领域排名条目。composite_score = 收益×0.5 + 夏普×0.3 + 回撤质量×0.2（域内归一化）。"""

    strategy_id: str
    domain: str
    composite_score: float
    rank_in_domain: int


class CrossCheck(BaseModel):
    """双轨交叉验证结果（T15）。"""

    strategy_id: str
    backtest_monthly_return: float  # 年化收益 / 12
    forward_return: float
    relative_diff: float  # |fwd - bt_monthly| / |bt_monthly|
    suspicious: bool  # relative_diff > threshold


class ArenaRunResult(BaseModel):
    """一次竞技场运行的汇总产物（T17 集成入口输出）。"""

    strategies: list[Strategy]
    fast_results: list[BacktestResult]
    precise_results: list[BacktestResult]
    rankings: list[ArenaRanking]
