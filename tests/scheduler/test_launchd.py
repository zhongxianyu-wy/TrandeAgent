"""T07-T09: launchd_scheduler 测试（plan §5 / spec FR-1 / AC-5）。

plist 生成做字段校验；install/uninstall/is_installed 用 mock subprocess，
绝不真正调用 launchctl load（plan §5 测试策略 4）。
"""
from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scheduler.config import SchedulerConfig
from src.scheduler.launchd_scheduler import LaunchdScheduler


@pytest.fixture
def launchd_home(tmp_path: Path, monkeypatch):
    """把 Path.home() 重定向到 tmp_path，避免污染真实 ~/Library。"""
    monkeypatch.setattr("src.scheduler.config.Path.home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr("src.scheduler.launchd_scheduler.Path.home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.fixture
def sched(tmp_path: Path, launchd_home):
    cfg = SchedulerConfig(
        state_dir=str(tmp_path / "state"),
        project_root=str(tmp_path),
    )
    return LaunchdScheduler(cfg, state_dir=cfg.state_path, today=date(2026, 7, 7))


# ---- T07 plist 模板 ----

class TestRenderPlist:
    def test_valid_xml(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        # 能被 XML 解析器解析
        root = ET.fromstring(xml)
        assert root.tag == "plist"

    def test_label_field(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        assert f"<string>{sched.config.label}</string>" in xml

    def test_trigger_time_fields(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        # 默认 16:00
        assert "<key>Hour</key><integer>16</integer>" in xml
        assert "<key>Minute</key><integer>0</integer>" in xml

    def test_trigger_time_custom(self, tmp_path: Path, launchd_home):
        cfg = SchedulerConfig(
            state_dir=str(tmp_path / "state"),
            project_root=str(tmp_path),
            trigger_time="09:30",
        )
        sched = LaunchdScheduler(cfg, state_dir=cfg.state_path)
        xml = sched.render_plist()
        assert "<key>Hour</key><integer>9</integer>" in xml
        assert "<key>Minute</key><integer>30</integer>" in xml

    def test_program_arguments(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        assert "<string>/usr/bin/env</string>" in xml
        assert "PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin" in xml
        assert "<string>python</string>" in xml
        assert "<string>src.main</string>" in xml
        assert "<string>daily</string>" in xml

    def test_log_and_working_dir_paths(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        assert "<key>StandardOutPath</key>" in xml
        assert "<key>StandardErrorPath</key>" in xml
        assert "<key>WorkingDirectory</key>" in xml
        assert str(sched.config.working_dir) in xml

    def test_plist_has_doctype(self, sched: LaunchdScheduler):
        xml = sched.render_plist()
        assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
        assert "DOCTYPE plist" in xml


# ---- T08 install/uninstall ----

class TestInstallUninstall:
    def test_install_writes_plist_and_loads(self, sched: LaunchdScheduler, mocker):
        mock_run = mocker.patch("subprocess.run")
        sched.install()
        # plist 文件已写入
        assert sched.config.launchd_plist_path.is_file()
        content = sched.config.launchd_plist_path.read_text(encoding="utf-8")
        assert sched.config.label in content
        # 调用了 launchctl load
        load_calls = [c for c in mock_run.call_args_list if c.args[0][0] == "launchctl" and c.args[0][1] == "load"]
        assert len(load_calls) == 1
        # 日志目录已创建
        assert sched.config.stdout_log.parent.is_dir()

    def test_install_is_idempotent(self, sched: LaunchdScheduler, mocker):
        """已安装时先 unload 再 load（幂等）。"""
        mocker.patch("subprocess.run")
        sched.install()
        # 再次安装
        sched.install()
        assert sched.config.launchd_plist_path.is_file()

    def test_install_creates_plist_dir(self, sched: LaunchdScheduler, mocker):
        mocker.patch("subprocess.run")
        # LaunchAgents 目录不存在
        assert not sched.config.launchd_plist_path.parent.exists()
        sched.install()
        assert sched.config.launchd_plist_path.parent.is_dir()

    def test_uninstall_removes_plist(self, sched: LaunchdScheduler, mocker):
        mocker.patch("subprocess.run")
        sched.install()
        assert sched.config.launchd_plist_path.is_file()
        sched.uninstall()
        assert not sched.config.launchd_plist_path.is_file()
        # 调用了 unload
        run_calls = [c.args[0] for c in subprocess.run.call_args_list]
        unload_calls = [c for c in run_calls if c[0] == "launchctl" and c[1] == "unload"]
        assert len(unload_calls) >= 1

    def test_uninstall_no_plist_is_noop(self, sched: LaunchdScheduler, mocker):
        mock_run = mocker.patch("subprocess.run")
        # 未安装直接卸载，不应抛错
        sched.uninstall()
        assert not sched.config.launchd_plist_path.exists()

    def test_install_load_failure_propagates(self, sched: LaunchdScheduler, mocker):
        """launchctl load 失败应抛 CalledProcessError。"""
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "launchctl"),
        )
        with pytest.raises(subprocess.CalledProcessError):
            sched.install()


# ---- T09 is_installed ----

class TestIsInstalled:
    def test_not_installed_when_no_plist_no_launchctl(self, sched: LaunchdScheduler, mocker):
        mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b""))
        assert sched.is_installed() is False

    def test_installed_when_plist_exists(self, sched: LaunchdScheduler, mocker):
        mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b""))
        sched.config.launchd_plist_path.parent.mkdir(parents=True, exist_ok=True)
        sched.config.launchd_plist_path.write_text("plist", encoding="utf-8")
        assert sched.is_installed() is True

    def test_installed_when_in_launchctl_list(self, sched: LaunchdScheduler, mocker):
        """plist 不在但 launchctl list 能查到（已加载）。"""
        mocker.patch(
            "subprocess.run",
            return_value=MagicMock(returncode=0, stdout=b"com.trandeagent.daily\n", stderr=b""),
        )
        assert sched.is_installed() is True

    def test_launchctl_list_failure_returns_false(self, sched: LaunchdScheduler, mocker):
        mocker.patch(
            "subprocess.run",
            side_effect=subprocess.CalledProcessError(1, "launchctl"),
        )
        assert sched.is_installed() is False

    def test_launchctl_oserror_returns_false(self, sched: LaunchdScheduler, mocker):
        mocker.patch("subprocess.run", side_effect=OSError("not found"))
        assert sched.is_installed() is False


# ---- Scheduler 抽象接口实现 ----

class TestSchedulerInterface:
    def test_should_run_today_trading_day(self, sched: LaunchdScheduler):
        assert sched.should_run_today(date(2026, 7, 7)) is True  # 周二

    def test_should_run_today_weekend(self, sched: LaunchdScheduler):
        assert sched.should_run_today(date(2026, 7, 5)) is False  # 周日

    def test_should_run_today_holiday(self, sched: LaunchdScheduler):
        assert sched.should_run_today(date(2024, 10, 1)) is False  # 国庆

    def test_record_run_writes_state(self, sched: LaunchdScheduler):
        sched.record_run("success", 200, "daily")
        last = sched.state.load_last_run()
        assert last["last_status"] == "success"
        assert last["last_duration_sec"] == 200
        hist = sched.state.read_history()
        assert len(hist) == 1
        assert hist[0]["mode"] == "daily"

    def test_is_subclass_of_scheduler(self, sched: LaunchdScheduler):
        from src.scheduler.scheduler import Scheduler
        assert isinstance(sched, Scheduler)
