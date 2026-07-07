"""集成测试：4433 法则端到端（AC-1）+ CLI 入口。

用 mock DataProvider + mock IndicatorEngine（构造样例指标 DataFrame），
不依赖真实网络。
"""
from __future__ import annotations

import pandas as pd
import pytest

from src.screener import __main__ as cli
from src.screener.engine import DefaultScreener
from src.screener.models import Rule, ScreenerConfig
from src.screener.presets import preset_4433
from tests.screener.conftest import MockDataProvider, MockIndicatorEngine


class TestScreenE2E:
    """AC-1：4433 法则端到端。"""

    def test_4433_returns_topn(self, sample_indicators):
        screener = DefaultScreener()
        result = screener.screen(preset_4433(), sample_indicators)
        assert not result.empty
        assert len(result) <= preset_4433().top_n

    def test_4433_each_candidate_has_matches(self, sample_indicators):
        """AC-1：每只候选基金命中至少 1 条规则，优胜者 >= 3。"""
        screener = DefaultScreener()
        result = screener.screen(preset_4433(), sample_indicators)
        for _, row in result.iterrows():
            assert len(row["matched_rules"]) >= 1
        assert len(result.iloc[0]["matched_rules"]) >= 3

    def test_4433_has_reason(self, sample_indicators):
        """AC-1：附选中理由。"""
        screener = DefaultScreener()
        result = screener.screen(preset_4433(), sample_indicators)
        for _, row in result.iterrows():
            assert isinstance(row["reason"], str) and row["reason"]

    def test_4433_explain_has_detail(self, sample_indicators):
        screener = DefaultScreener()
        result = screener.screen(preset_4433(), sample_indicators)
        text = screener.explain(
            result.iloc[0]["fund_code"], result.iloc[0]["matched_rules"]
        )
        assert "规则" in text


class TestRunScreen:
    """run_screen 编排：拉基金 → 批量算指标 → 筛选。"""

    def test_with_injected_mocks(self, mock_provider, mock_engine):
        result = cli.run_screen(
            preset_4433(), provider=mock_provider, engine=mock_engine
        )
        assert not result.empty
        assert "fund_code" in result.columns
        assert mock_engine.calc_batch_called == 1

    def test_empty_funds(self, mock_engine):
        provider = MockDataProvider()
        provider.list_funds = lambda categories=None: pd.DataFrame()  # type: ignore
        result = cli.run_screen(
            preset_4433(), provider=provider, engine=mock_engine
        )
        assert result.empty


class TestCli:
    def test_presets_command(self, capsys):
        rc = cli.main(["presets"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "rule_4433" in out

    def test_run_command_with_mocks(
        self, monkeypatch, capsys, mock_provider, mock_engine
    ):
        monkeypatch.setattr(cli, "build_provider", lambda: mock_provider)
        monkeypatch.setattr(cli, "build_engine", lambda provider, years=5: mock_engine)
        rc = cli.main(["run", "--top", "3"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "F001" in out

    def test_run_command_empty(self, monkeypatch, capsys):
        provider = MockDataProvider()
        provider.list_funds = lambda categories=None: pd.DataFrame()  # type: ignore
        monkeypatch.setattr(cli, "build_provider", lambda: provider)
        monkeypatch.setattr(
            cli, "build_engine", lambda p, years=5: MockIndicatorEngine()
        )
        rc = cli.main(["run"])
        assert rc == 0

    def test_resolve_config_default(self):
        args = type("A", (), {"rules": None, "preset": None})()
        cfg = cli.resolve_config(args)
        assert isinstance(cfg, ScreenerConfig)

    def test_resolve_config_preset(self):
        args = type("A", (), {"rules": None, "preset": "rule_4433"})()
        cfg = cli.resolve_config(args)
        assert isinstance(cfg, ScreenerConfig)
        assert len(cfg.rules) >= 3

    def test_resolve_config_rules_file(self, tmp_path):
        p = tmp_path / "custom.yaml"
        p.write_text(
            "rules:\n"
            "  - name: r1\n"
            "    field: sharpe\n"
            "    op: '>='\n"
            "    value: 1.0\n"
            "top_n: 5\n",
            encoding="utf-8",
        )
        args = type("A", (), {"rules": str(p), "preset": None})()
        cfg = cli.resolve_config(args)
        assert cfg.top_n == 5
        assert cfg.rules[0].name == "r1"

    def test_run_overrides_top_n(self, monkeypatch, mock_provider, mock_engine):
        monkeypatch.setattr(cli, "build_provider", lambda: mock_provider)
        monkeypatch.setattr(cli, "build_engine", lambda provider, years=5: mock_engine)
        # top_n=1 → 最多 1 条
        result = cli.run_screen(
            preset_4433().model_copy(update={"top_n": 1}),
            provider=mock_provider,
            engine=mock_engine,
        )
        assert len(result) <= 1


class TestFieldPathAdaptation:
    """字段路径同时兼容嵌套与扁平列名（plan 技术约束）。"""

    def test_flat_columns(self, sample_indicators):
        cfg = ScreenerConfig(
            rules=[Rule(name="r1", field="sharpe", op=">=", value=1.0)],
            weights={},
            top_n=20,
        )
        result = DefaultScreener().screen(cfg, sample_indicators)
        # sharpe>=1.0：F001~F005（1.8,1.6,1.4,1.2,1.0）
        assert len(result) == 5

    def test_nested_path_resolves_to_flat(self, sample_indicators):
        cfg = ScreenerConfig(
            rules=[
                Rule(name="r1", field="l2_performance.sharpe", op=">=", value=1.0)
            ],
            weights={},
            top_n=20,
        )
        result = DefaultScreener().screen(cfg, sample_indicators)
        assert len(result) == 5
