"""FundScreener 抽象接口 + DefaultScreener 实现（T02, T08, T09）。

对应 plan §3 接口契约。screen 对全批指标做向量化筛选与加权打分，
explain 输出"为什么被选中"的中文理由（命中规则 + 实际指标值）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from src.screener.models import Rule, ScreenerConfig
from src.screener.rules import apply_rule, resolve_field
from src.screener.scorer import score_fund

# 常见字段的中文标签，用于解释输出（缺失则用字段名）
_FIELD_LABELS: dict[str, str] = {
    "scale": "规模(亿)",
    "establish_years": "成立年限",
    "manager_tenure_years": "经理任期(年)",
    "institution_holding_pct": "机构占比",
    "management_fee": "管理费率",
    "custodian_fee": "托管费率",
    "return_1y": "近1年收益",
    "return_3y": "近3年收益",
    "return_5y": "近5年收益",
    "rank_1y_percentile": "近1年排名百分位",
    "max_drawdown": "最大回撤",
    "sharpe": "夏普比率",
    "volatility": "波动率",
    "alpha": "alpha",
    "beta": "beta",
    "style_box": "风格箱",
    "industry_concentration_top3": "行业集中度",
    "holding_turnover": "持仓换手率",
    "style_drift_score": "风格漂移",
    "share_change_yoy": "份额同比变动",
    "institution_holding_change": "机构持有变化",
    "dividend_count_5y": "近5年分红次数",
}


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(field.split(".")[-1], field)


def _format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.4g}"
    return str(value)


def _rule_criterion(rule: Rule) -> str:
    """把规则的判定条件格式化成可读文本。"""
    label = _field_label(rule.field)
    v = _format_value(rule.value)
    if rule.op == ">=":
        return f"{label} >= {v}"
    if rule.op == "<=":
        return f"{label} <= {v}"
    if rule.op == "between":
        low, high = rule.value
        return f"{label} 在 [{_format_value(low)}, {_format_value(high)}]"
    if rule.op == "in":
        return f"{label} 属于 {rule.value}"
    if rule.op == "percentile_top":
        return f"{label} 同类前 {_format_value(float(rule.value) * 100)}%"
    return f"{label} {rule.op} {v}"


class FundScreener(ABC):
    """基金筛选器抽象。"""

    @abstractmethod
    def screen(
        self, config: ScreenerConfig, all_indicators: pd.DataFrame
    ) -> pd.DataFrame:
        """按配置筛选并打分，返回 Top-N 候选。

        Args:
            config: 筛选规则配置。
            all_indicators: 一行一基金的指标 DataFrame（calc_batch 产物）。

        Returns:
            DataFrame，按得分降序，列：fund_code, score, matched_rules, reason。
        """

    @abstractmethod
    def explain(self, fund_code: str, matched_rules: list[str]) -> str:
        """生成"为什么被选中"的中文理由。"""


class DefaultScreener(FundScreener):
    """默认筛选器：向量化规则匹配 + 加权打分。"""

    def __init__(self) -> None:
        # 缓存上一次 screen 的上下文，供 explain 查指标实际值
        self._last_config: ScreenerConfig | None = None
        self._last_indicators: pd.DataFrame | None = None

    # ------------------------------------------------------------------
    # screen
    # ------------------------------------------------------------------
    def screen(
        self, config: ScreenerConfig, all_indicators: pd.DataFrame
    ) -> pd.DataFrame:
        if all_indicators is None or all_indicators.empty:
            return pd.DataFrame(
                columns=["fund_code", "score", "matched_rules", "reason"]
            )

        df = all_indicators.reset_index(drop=True)

        # 逐规则计算布尔掩码，组成 (n_funds, n_rules) 命中矩阵
        masks: list[pd.Series] = []
        for rule in config.rules:
            masks.append(apply_rule(rule, df).fillna(False).astype(bool))

        # 每只基金命中的规则名列表
        matched_list: list[list[str]] = []
        scores: list[float] = []
        for i in range(len(df)):
            matched = [
                config.rules[j].name
                for j, m in enumerate(masks)
                if bool(m.iloc[i])
            ]
            matched_list.append(matched)
            scores.append(score_fund(matched, config))

        df = df.copy()
        df["matched_rules"] = matched_list
        df["score"] = scores

        # 缓存上下文供 explain 使用
        self._last_config = config
        self._last_indicators = df

        # 仅保留至少命中 1 条的基金，按得分降序取 Top-N
        result = df[df["score"] > 0].copy()
        result = result.sort_values(
            ["score", "fund_code"], ascending=[False, True]
        ).head(config.top_n)

        result["reason"] = [
            self._build_reason(row, config)
            for _, row in result.iterrows()
        ]

        return result[
            ["fund_code", "score", "matched_rules", "reason"]
        ].reset_index(drop=True)

    # ------------------------------------------------------------------
    # explain
    # ------------------------------------------------------------------
    def explain(self, fund_code: str, matched_rules: list[str]) -> str:
        config = self._last_config
        indicators = self._last_indicators
        if config is None:
            return f"基金 {fund_code} 命中规则：{'、'.join(matched_rules) or '无'}"

        rule_map = {r.name: r for r in config.rules}
        lines = [f"基金 {fund_code} 命中 {len(matched_rules)} 条规则："]
        for name in matched_rules:
            rule = rule_map.get(name)
            if rule is None:
                lines.append(f"- {name}")
                continue
            lines.append(f"- {name}：{_rule_criterion(rule)}")
            # 附实际指标值（若可查）
            actual = self._lookup_actual(rule, fund_code, indicators)
            if actual is not None:
                lines.append(f"    当前 {_field_label(rule.field)} = {actual}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 内部
    # ------------------------------------------------------------------
    def _build_reason(self, row: pd.Series, config: ScreenerConfig) -> str:
        """为 screen 结果行生成精简理由。"""
        matched: list[str] = row["matched_rules"]
        rule_map = {r.name: r for r in config.rules}
        parts = []
        for name in matched:
            rule = rule_map.get(name)
            if rule is None:
                parts.append(name)
                continue
            actual = self._format_actual(rule, row)
            crit = _rule_criterion(rule)
            if actual is not None:
                parts.append(f"{rule.name}（{crit}，当前 {actual}）")
            else:
                parts.append(f"{rule.name}（{crit}）")
        return "；".join(parts)

    def _lookup_actual(
        self, rule: Rule, fund_code: str, indicators: pd.DataFrame | None
    ) -> str | None:
        if indicators is None or indicators.empty:
            return None
        try:
            row = indicators[indicators["fund_code"].astype(str) == fund_code]
            if row.empty:
                return None
            val = resolve_field(indicators, rule.field).iloc[
                int(row.index[0])
            ]
            return _format_value(val)
        except (KeyError, IndexError):
            return None

    def _format_actual(self, rule: Rule, row: pd.Series) -> str | None:
        try:
            val = resolve_field(
                row.to_frame().T, rule.field
            ).iloc[0]
            return _format_value(val)
        except (KeyError, IndexError):
            return None
