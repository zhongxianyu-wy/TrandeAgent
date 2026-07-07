"""T17: CLI 与 __main__ 测试。"""
from __future__ import annotations

import pytest

from src.arena.__main__ import main


class TestCLI:
    def test_run_command_exits_zero(self, capsys):
        rc = main(["run", "--count", "5"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "竞技场" in out

    def test_run_with_all_args(self):
        rc = main(["run", "--count", "100", "--fund-code", "110011", "--years", "3", "--write-base"])
        assert rc == 0

    def test_no_command_prints_help(self, capsys):
        with pytest.raises(SystemExit):
            main([])
