"""T02 / T09：FundScreener 抽象接口 + DefaultScreener（screen / explain）测试。"""
from __future__ import annotations

import pandas as pd
import pytest

from src.screener.engine import DefaultScreener, FundScreener
from src.screener.models import Rule, ScreenerConfig
from src.screener.presets import preset_4433


class TestAbstractInterface:
    def test_cannot_instantiate_abstract(self):
        with pytest.raises(TypeError):
            FundScreener()  # type: ignore[abstract]


@pytest.fixture
def screener():
    return DefaultScreener()


class TestScreen:
    def test_returns_expected_columns(self, screener, sample_indicators):
        result = screener.screen(preset_4433(), sample_indicators)
        assert list(result.columns) == ["fund_code", "score", "matched_rules", "reason"]

    def test_sorted_by_score_desc(self, screener, sample_indicators):
        result = screener.screen(preset_4433(), sample_indicators)
        scores = result["score"].tolist()
        assert scores == sorted(scores, reverse=True)

    def test_top_fund_is_winner(self, screener, sample_indicators):
        """AC-1：F001（业绩/夏普均领先 + 规模适中）应排第一。"""
        result = screener.screen(preset_4433(), sample_indicators)
        assert result.iloc[0]["fund_code"] == "F001"
        assert result.iloc[0]["score"] > 0

    def test_winner_matches_at_least_3_rules(self, screener, sample_indicators):
        """AC-1：候选基金命中至少 3 条规则。"""
        result = screener.screen(preset_4433(), sample_indicators)
        assert len(result.iloc[0]["matched_rules"]) >= 3

    def test_all_results_have_positive_score(self, screener, sample_indicators):
        result = screener.screen(preset_4433(), sample_indicators)
        assert (result["score"] > 0).all()

    def test_top_n_limit(self, screener, sample_indicators):
        cfg = preset_4433().model_copy(update={"top_n": 2})
        result = screener.screen(cfg, sample_indicators)
        assert len(result) <= 2

    def test_empty_indicators(self, screener):
        result = screener.screen(preset_4433(), pd.DataFrame())
        assert result.empty
        assert list(result.columns) == ["fund_code", "score", "matched_rules", "reason"]

    def test_none_indicators(self, screener):
        result = screener.screen(preset_4433(), None)
        assert result.empty

    def test_no_fund_matches_returns_empty(self, screener, sample_indicators):
        """所有规则都不可能命中 → 空结果。"""
        cfg = ScreenerConfig(
            rules=[Rule(name="impossible", field="sharpe", op=">=", value=999.0)],
            weights={},
            top_n=5,
        )
        result = screener.screen(cfg, sample_indicators)
        assert result.empty

    def test_score_uses_weights(self, screener, sample_indicators):
        """权重影响得分排序。"""
        cfg = ScreenerConfig(
            rules=[
                Rule(name="r1", field="sharpe", op=">=", value=1.0),
                Rule(name="r2", field="scale", op="between", value=[2.0, 50.0]),
            ],
            weights={"r1": 10.0, "r2": 0.1},
            top_n=20,
        )
        result = screener.screen(cfg, sample_indicators)
        # F001 同时命中 r1(sharpe>=1.8) 与 r2(scale=27 在范围)
        winner = result.iloc[0]
        assert "r1" in winner["matched_rules"]

    def test_reason_contains_rule_info(self, screener, sample_indicators):
        result = screener.screen(preset_4433(), sample_indicators)
        reason = result.iloc[0]["reason"]
        assert isinstance(reason, str)
        assert len(reason) > 0


class TestExplain:
    def test_explain_after_screen(self, screener, sample_indicators):
        screener.screen(preset_4433(), sample_indicators)
        first = screener.screen(preset_4433(), sample_indicators).iloc[0]
        text = screener.explain(first["fund_code"], first["matched_rules"])
        assert isinstance(text, str)
        assert first["fund_code"] in text
        assert "规则" in text

    def test_explain_includes_actual_value(self, screener, sample_indicators):
        screener.screen(preset_4433(), sample_indicators)
        first = screener.screen(preset_4433(), sample_indicators).iloc[0]
        text = screener.explain(first["fund_code"], first["matched_rules"])
        # 应包含某指标的实际值（如夏普）
        assert "当前" in text

    def test_explain_without_screen_context(self):
        """未先 screen 时给出兜底说明。"""
        s = DefaultScreener()
        text = s.explain("F001", ["r1", "r2"])
        assert "F001" in text
        assert "r1" in text

    def test_explain_empty_rules(self, screener, sample_indicators):
        screener.screen(preset_4433(), sample_indicators)
        text = screener.explain("F001", [])
        assert isinstance(text, str)


class TestExplainFormatting:
    """覆盖各操作符的条件格式化分支。"""

    def test_explain_le_and_in(self, screener, sample_indicators):
        cfg = ScreenerConfig(
            rules=[
                Rule(name="dd", field="l2_performance.max_drawdown", op="<=", value=-0.2),
                Rule(name="box", field="l3_style.style_box", op="in", value=["大盘成长"]),
            ],
            weights={},
            top_n=20,
        )
        result = screener.screen(cfg, sample_indicators)
        if not result.empty:
            first = result.iloc[0]
            reason = first["reason"]
            text = screener.explain(first["fund_code"], first["matched_rules"])
            assert "<=" in reason or "属于" in reason
            assert isinstance(text, str)

    def test_explain_quality_preset(self, screener, sample_indicators):
        """quality 预设使用 >= 运算符，覆盖不同字段标签。"""
        from src.screener.presets import preset_quality

        result = screener.screen(preset_quality(), sample_indicators)
        if not result.empty:
            first = result.iloc[0]
            text = screener.explain(first["fund_code"], first["matched_rules"])
            assert isinstance(text, str)
            assert "规则" in text
