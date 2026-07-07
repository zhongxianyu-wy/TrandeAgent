"""T03-T07：5 个运算符 + 字段解析测试。"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.screener.models import Rule
from src.screener.rules import (
    OPERATORS,
    apply_rule,
    op_between,
    op_ge,
    op_in,
    op_le,
    op_percentile_top,
    resolve_field,
)


@pytest.fixture
def df():
    return pd.DataFrame(
        {
            "fund_code": ["A", "B", "C", "D"],
            "sharpe": [1.8, 1.0, 0.4, -0.1],
            "l2_performance.sharpe": [1.8, 1.0, 0.4, -0.1],  # 嵌套同名列
            "scale": [27.0, 1.0, 15.0, 480.0],
            "style_box": ["大盘成长", "中盘价值", "大盘成长", "小盘价值"],
            "max_drawdown": [-0.15, -0.22, -0.30, -0.40],
        }
    )


class TestResolveField:
    def test_flat_column(self, df):
        s = resolve_field(df, "sharpe")
        assert list(s) == [1.8, 1.0, 0.4, -0.1]

    def test_nested_path_falls_back_to_flat(self, df):
        # 路径 l2_performance.sharpe：无精确列时取最后一段 "sharpe"
        s = resolve_field(df.drop(columns=["l2_performance.sharpe"]), "l2_performance.sharpe")
        assert list(s) == [1.8, 1.0, 0.4, -0.1]

    def test_nested_exact_column_preferred(self, df):
        s = resolve_field(df, "l2_performance.sharpe")
        assert list(s) == [1.8, 1.0, 0.4, -0.1]

    def test_missing_field_raises(self, df):
        with pytest.raises(KeyError):
            resolve_field(df, "nonexistent.field")


class TestOpGe:
    def test_ge(self, df):
        mask = op_ge(df["sharpe"], 1.0)
        assert list(mask) == [True, True, False, False]


class TestOpLe:
    def test_le(self, df):
        mask = op_le(df["scale"], 15.0)
        assert list(mask) == [False, True, True, False]


class TestOpBetween:
    def test_between(self, df):
        mask = op_between(df["scale"], [2.0, 50.0])
        assert list(mask) == [True, False, True, False]

    def test_between_inclusive(self, df):
        mask = op_between(df["scale"], [27.0, 27.0])
        assert list(mask) == [True, False, False, False]

    def test_between_invalid_value(self, df):
        with pytest.raises(ValueError):
            op_between(df["scale"], 5.0)
        with pytest.raises(ValueError):
            op_between(df["scale"], [1.0])


class TestOpIn:
    def test_in(self, df):
        # df fixture: style_box = [大盘成长, 中盘价值, 大盘成长, 小盘价值]
        mask = op_in(df["style_box"], ["大盘成长", "小盘价值"])
        assert list(mask) == [True, False, True, True]

    def test_in_invalid_value(self, df):
        with pytest.raises(ValueError):
            op_in(df["style_box"], "大盘成长")


class TestOpPercentileTop:
    def test_top_third(self):
        # 0..9 共 10 个值，top 30% → 前三个最大值命中
        s = pd.Series(np.arange(10.0))
        mask = op_percentile_top(s, 0.3)
        assert mask.sum() >= 3
        # 最大值必命中，最小值必不命中
        assert mask.iloc[-1]
        assert not mask.iloc[0]

    def test_invalid_fraction(self):
        s = pd.Series([1.0, 2.0, 3.0])
        with pytest.raises(ValueError):
            op_percentile_top(s, 0.0)
        with pytest.raises(ValueError):
            op_percentile_top(s, 1.0)

    def test_higher_is_better(self):
        # 确认取的是值最大的那批
        s = pd.Series([0.1, 0.5, 0.9, 0.2, 0.8])
        mask = op_percentile_top(s, 0.4)
        assert mask.iloc[2]  # 0.9 命中
        assert mask.iloc[4]  # 0.8 命中
        assert not mask.iloc[0]  # 0.1 不命中


class TestApplyRule:
    def test_apply_ge_rule(self, df):
        rule = Rule(name="sharpe_ge1", field="sharpe", op=">=", value=1.0)
        mask = apply_rule(rule, df)
        assert list(mask) == [True, True, False, False]

    def test_apply_nested_field(self, df):
        rule = Rule(
            name="sharpe_ge1", field="l2_performance.sharpe", op=">=", value=1.0
        )
        mask = apply_rule(rule, df.drop(columns=["l2_performance.sharpe"]))
        assert list(mask) == [True, True, False, False]

    def test_apply_unknown_op_raises(self, df, monkeypatch):
        """运算符不在注册表中 → ValueError（防御性分支）。"""
        rule = Rule(name="r", field="sharpe", op=">=", value=1.0)
        monkeypatch.setattr("src.screener.rules.OPERATORS", {})
        with pytest.raises(ValueError):
            apply_rule(rule, df)

    def test_operators_registry_complete(self):
        assert set(OPERATORS.keys()) == {">=", "<=", "between", "in", "percentile_top"}
