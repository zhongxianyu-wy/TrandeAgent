"""T00/T01: CLI (__main__) 测试 — doctor / health / install-cli。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.feishu import __main__ as feishu_main


class TestDoctorCmd:
    def test_doctor_not_installed_returns_1(self, monkeypatch, capsys):
        monkeypatch.setattr(feishu_main, "detect_lark_cli", lambda: None)
        monkeypatch.setattr(feishu_main, "detect_shell", lambda: "zsh")
        rc = feishu_main.cmd_doctor()
        out = capsys.readouterr().out
        assert rc == 1
        assert "npm install -g @larksuite/cli" in out

    def test_doctor_installed_returns_0(self, monkeypatch, capsys):
        monkeypatch.setattr(feishu_main, "detect_lark_cli", lambda: "/fake/lark-cli")
        monkeypatch.setattr(feishu_main, "detect_shell", lambda: "zsh")
        rc = feishu_main.cmd_doctor()
        out = capsys.readouterr().out
        assert rc == 0
        assert "已安装" in out

    def test_detect_shell_returns_string(self, monkeypatch):
        monkeypatch.setenv("SHELL", "/bin/zsh")
        # shellingham 可能不可用，回退到 SHELL
        result = feishu_main.detect_shell()
        assert isinstance(result, str)


class TestHealthCmd:
    def test_health_reports_missing(self, monkeypatch, tmp_path, capsys):
        # 无凭证、无 cli、无 base → advice 非空
        cfg_path = tmp_path / "feishu.yaml"
        cfg_path.write_text("user_open_id: 'ou_x'\n", encoding="utf-8")
        monkeypatch.setattr(feishu_main, "_CONFIG_PATH", str(cfg_path))
        monkeypatch.setattr(feishu_main, "LarkCLIClient", _FailingCliClient)
        rc = feishu_main.cmd_health()
        out = capsys.readouterr().out
        assert rc == 1
        assert "修复建议" in out

    def test_health_all_ok(self, monkeypatch, tmp_path, capsys):
        cfg_path = tmp_path / "feishu.yaml"
        cfg_path.write_text(
            "app_id: 'a'\napp_secret: 'b'\nbase_token: 'basX'\n", encoding="utf-8"
        )
        monkeypatch.setattr(feishu_main, "_CONFIG_PATH", str(cfg_path))
        # mock lark-cli 已安装（本机真实未安装）
        monkeypatch.setattr(
            feishu_main.LarkCLIClient, "_find_cli", lambda self: "/fake/lark-cli"
        )
        rc = feishu_main.cmd_health()
        out = capsys.readouterr().out
        assert rc == 0
        assert "全部就绪" in out


class TestMainDispatch:
    def test_main_doctor_dispatch(self, monkeypatch):
        called = {"cmd": None}
        monkeypatch.setattr(feishu_main, "cmd_doctor", lambda: called.__setitem__("cmd", "doc") or 0)
        rc = feishu_main.main(["doctor"])
        assert rc == 0 and called["cmd"] == "doc"

    def test_main_test_push_dispatch(self, monkeypatch):
        monkeypatch.setattr(feishu_main, "cmd_test_push", lambda: 0)
        assert feishu_main.main(["test-push"]) == 0

    def test_main_init_dispatch(self, monkeypatch):
        monkeypatch.setattr(feishu_main, "cmd_init", lambda: 0)
        assert feishu_main.main(["init"]) == 0

    def test_main_requires_subcommand(self):
        with pytest.raises(SystemExit):
            feishu_main.main([])


class TestInstallCli:
    def test_install_already_installed(self, monkeypatch):
        monkeypatch.setattr(feishu_main, "detect_lark_cli", lambda: "/fake/lark-cli")
        assert feishu_main.cmd_install_cli() == 0

    def test_install_no_npm(self, monkeypatch):
        monkeypatch.setattr(feishu_main, "detect_lark_cli", lambda: None)
        monkeypatch.setattr(feishu_main, "shutil", _FakeShutil(which=lambda *a, **k: None))
        assert feishu_main.cmd_install_cli() == 1

    def test_install_runs_npm(self, monkeypatch):
        called = {}

        class _R:
            returncode = 0

        def _run(cmd, env=None):
            called["cmd"] = cmd
            return _R()

        monkeypatch.setattr(feishu_main, "detect_lark_cli", lambda: None)
        monkeypatch.setattr(feishu_main, "shutil", _FakeShutil(which=lambda *a, **k: "/usr/bin/npm"))
        monkeypatch.setattr(feishu_main, "subprocess", _FakeSubprocess(_run))
        assert feishu_main.cmd_install_cli() == 0
        assert "npm" in called["cmd"]


# --- helpers -----------------------------------------------------------
class _FailingCliClient:
    def __init__(self, config, config_path=None):
        self.config = config

    def health_check(self):
        return {"lark_cli": False, "token": False, "base": False, "advice": ["x"]}


class _FakeShutil:
    def __init__(self, which):
        self.which = which


class _FakeSubprocess:
    def __init__(self, run):
        self.run = run
        self.CompletedProcess = __import__("subprocess").CompletedProcess
