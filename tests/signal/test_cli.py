"""T12：CLI 入口测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.signal import __main__ as cli
from src.signal.models import SignalRule


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "signals.yaml"


class TestLoadRules:
    def test_loads_real_config(self):
        rules, threshold = cli.load_rules(CONFIG_PATH)
        assert len(rules) > 0
        assert all(isinstance(r, SignalRule) for r in rules)
        assert threshold == -3.0
        # 含三类规则
        cats = {r.category for r in rules}
        assert {"technical", "fundamental", "fund_specific"} <= cats

    def test_missing_config_returns_empty(self, tmp_path):
        rules, threshold = cli.load_rules(tmp_path / "nope.yaml")
        assert rules == []
        assert threshold == -3.0


class TestParser:
    def test_calc_requires_codes(self):
        parser = cli.build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["calc"])

    def test_alert_parses(self):
        parser = cli.build_parser()
        args = parser.parse_args(["alert", "--code", "X", "--return", "-4.0"])
        assert args.code == "X"
        assert args.return_value == -4.0


class TestMainDemo:
    def test_demo_runs(self, capsys, monkeypatch):
        # 用真实 config（若不存在则走 _demo_rules）
        monkeypatch.chdir(REPO_ROOT)
        rc = cli.main(["demo"])
        assert rc == 0
        out = capsys.readouterr().out
        # 至少打印了表头与三只 demo 基金
        assert "DEMO_UP" in out
        assert "DEMO_DOWN" in out
        assert "DEMO_FLAT" in out


class TestMainAlert:
    def test_alert_triggered(self, capsys, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        # provider 初始化失败时会用无 provider 的 engine（detect_intraday_alert 仍可工作）
        rc = cli.main(["alert", "--code", "X", "--return", "-4.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "触发大跌警报" in out

    def test_alert_not_triggered(self, capsys, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        rc = cli.main(["alert", "--code", "X", "--return", "-1.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "未触发" in out

    def test_alert_custom_threshold(self, capsys, monkeypatch):
        monkeypatch.chdir(REPO_ROOT)
        rc = cli.main(["alert", "--code", "X", "--return", "-1.5",
                       "--threshold", "-1.0"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "触发大跌警报" in out


class TestMainCalc:
    def test_calc_no_rules_returns_error(self, capsys, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)  # config/signals.yaml 不存在
        rc = cli.main(["calc", "--codes", "X"])
        assert rc == 1
