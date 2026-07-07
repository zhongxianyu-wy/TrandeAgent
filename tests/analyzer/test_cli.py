"""T12: CLI 入口测试（mock 依赖，不触真实网络/LLM）。"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.analyzer.__main__ import main
from tests.analyzer.conftest import make_report


@pytest.fixture
def patched_analyzer(monkeypatch):
    fake = SimpleNamespace(analyze=lambda code: make_report(fund_code=code, label="建议"))
    monkeypatch.setattr(
        "src.analyzer.__main__._build_default_analyzer",
        lambda provider=None: fake,
    )
    return fake


class TestCLI:
    def test_analyze_requires_code(self):
        with pytest.raises(SystemExit):
            main(["analyze"])  # 缺 --code

    def test_analyze_success(self, patched_analyzer, capsys):
        rc = main(["analyze", "--code", "000001", "--markdown"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "000001" in out
        assert "经理画像" in out

    def test_analyze_provider_choice(self, patched_analyzer, capsys):
        rc = main(["analyze", "--code", "161725", "--provider", "qwen"])
        assert rc == 0

    def test_invalid_provider_rejected(self):
        with pytest.raises(SystemExit):
            main(["analyze", "--code", "000001", "--provider", "invalid"])

    def test_no_subcommand(self):
        with pytest.raises(SystemExit):
            main([])

    def test_batch_no_funds(self, monkeypatch):
        """配置无 funds 时 batch 返回非零。"""
        monkeypatch.setattr(
            "src.analyzer.__main__.load_analyzer_config",
            lambda: SimpleNamespace(funds=[], years=5, max_retries=1, llm=None),
        )
        rc = main(["batch"])
        assert rc == 1
