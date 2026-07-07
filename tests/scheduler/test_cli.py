"""T10: CLI 集成测试（plan §5 / spec FR-1,3,4）。

覆盖 install/uninstall/status/run（含 --force / --dry-run），
通过注入临时 state_dir + mock subprocess + runner 回调完成。
"""
from __future__ import annotations

import subprocess
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.scheduler.__main__ import main as cli_main
from src.scheduler.config import SchedulerConfig
from src.scheduler.launchd_scheduler import LaunchdScheduler


@pytest.fixture
def cli_env(tmp_path: Path, monkeypatch):
    """准备 CLI 测试环境：临时 home + state，返回构造 scheduler 的工厂。

    关键：patch 掉 main() 内部的 load_scheduler_config，让它返回 tmp 配置，
    否则 main 会从 config/scheduler.yaml 加载真实 state_dir。
    """
    monkeypatch.setattr("src.scheduler.config.Path.home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr("src.scheduler.launchd_scheduler.Path.home", classmethod(lambda cls: tmp_path))
    cfg = SchedulerConfig(
        state_dir=str(tmp_path / "state"),
        project_root=str(tmp_path),
    )
    # 让 main() 内 load_scheduler_config 返回本 cfg，避免污染真实 data/state
    monkeypatch.setattr("src.scheduler.__main__.load_scheduler_config", lambda *a, **k: cfg)
    return cfg


def _make_runner_calls():
    """返回 (runner, calls) — runner 记录调用到 calls。"""
    calls: list[tuple[date, str]] = []

    def runner(d: date, mode: str):
        calls.append((d, mode))
        return ("success", 30, 100)

    return runner, calls


class TestCliInstall:
    def test_install_command(self, cli_env, mocker, capsys):
        mocker.patch("subprocess.run")
        rc = cli_main(["install"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "已安装" in out
        assert cli_env.launchd_plist_path.is_file()

    def test_uninstall_command(self, cli_env, mocker, capsys):
        mocker.patch("subprocess.run")
        cli_main(["install"])
        rc = cli_main(["uninstall"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "已卸载" in out
        assert not cli_env.launchd_plist_path.exists()


class TestCliStatus:
    def test_status_no_history(self, cli_env, mocker, capsys):
        mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b""))
        rc = cli_main(["status"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "未安装" in out or "已安装" in out
        assert "无记录" in out

    def test_status_with_history(self, cli_env, mocker, capsys):
        mocker.patch("subprocess.run", return_value=MagicMock(returncode=0, stdout=b"", stderr=b""))
        # 预置状态
        sched = LaunchdScheduler(cli_env, state_dir=cli_env.state_path, today=date(2026, 7, 7))
        sched.state.save_last_run(date(2026, 7, 6), "2026-07-06T16:00:00+08:00", "success", 1820)
        rc = cli_main(["status"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "success" in out
        assert "2026-07-06" in out


class TestCliRun:
    def test_run_non_trading_day_skips(self, cli_env, monkeypatch, capsys):
        """周末运行应跳过（spec AC-2 / FR-2）。"""
        runner, calls = _make_runner_calls()
        # today 注入为周日，runner 不应被调用
        monkeypatch.setattr(
            "src.scheduler.__main__.LaunchdScheduler",
            lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 5), runner=runner, **kw),
        )
        rc = cli_main(["run"])
        assert rc == 0
        assert calls == []
        out = capsys.readouterr().out
        assert "非交易日" in out

    def test_run_trading_day_executes(self, cli_env, monkeypatch, capsys):
        """交易日运行调 runner 并记录（spec AC-1）。"""
        runner, calls = _make_runner_calls()
        monkeypatch.setattr(
            "src.scheduler.__main__.LaunchdScheduler",
            lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 7), runner=runner, **kw),
        )
        rc = cli_main(["run"])
        assert rc == 0
        assert len(calls) == 1
        assert calls[0][0] == date(2026, 7, 7)
        out = capsys.readouterr().out
        assert "运行完成" in out

    def test_run_force_on_weekend(self, cli_env, monkeypatch, capsys):
        """--force 在周末也运行（spec AC-4 / FR-4）。"""
        runner, calls = _make_runner_calls()
        monkeypatch.setattr(
            "src.scheduler.__main__.LaunchdScheduler",
            lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 5), runner=runner, **kw),
        )
        rc = cli_main(["run", "--force"])
        assert rc == 0
        assert len(calls) == 1
        assert calls[0][1] == "force"

    def test_run_dry_run_no_state_write(self, cli_env, monkeypatch, capsys):
        """--dry-run 模拟运行，不调 runner 不写状态（spec FR-4）。"""
        runner, calls = _make_runner_calls()
        monkeypatch.setattr(
            "src.scheduler.__main__.LaunchdScheduler",
            lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 7), runner=runner, **kw),
        )
        rc = cli_main(["run", "--dry-run"])
        assert rc == 0
        assert calls == []  # runner 未被调用
        # 状态文件未创建
        assert not cli_env.last_run_file.exists()
        out = capsys.readouterr().out
        assert "dry-run" in out

    def test_run_records_failed(self, cli_env, monkeypatch, capsys):
        """runner 抛异常应记 failed 并返回 1。"""
        def runner(d, mode):
            raise RuntimeError("boom")
        monkeypatch.setattr(
            "src.scheduler.__main__.LaunchdScheduler",
            lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 7), runner=runner, **kw),
        )
        rc = cli_main(["run"])
        assert rc == 1
        last = LaunchdScheduler(cli_env, state_dir=cli_env.state_path).state.load_last_run()
        assert last["last_status"] == "failed"

    def test_run_backfills_missed(self, cli_env, monkeypatch, capsys):
        """交易日运行时若有漏推送会先补发（spec FR-3 / AC-3）。"""
        runner, calls = _make_runner_calls()
        # 上次运行 07-03，today 07-07 → 漏 [07-06]
        sched_factory = lambda cfg, **kw: LaunchdScheduler(cfg, today=date(2026, 7, 7), runner=runner, **kw)
        monkeypatch.setattr("src.scheduler.__main__.LaunchdScheduler", sched_factory)
        # 先预置 last_run
        pre = sched_factory(cli_env, state_dir=cli_env.state_path)
        pre.state.save_last_run(date(2026, 7, 3), "2026-07-03T16:00:00+08:00", "success", 100)
        rc = cli_main(["run"])
        assert rc == 0
        # runner 被调两次：补发 07-06 + 当日 07-07
        assert len(calls) == 2
        assert calls[0] == (date(2026, 7, 6), "backfill")
        assert calls[1] == (date(2026, 7, 7), "daily")


class TestConfig:
    def test_load_scheduler_config_from_file(self, tmp_path):
        from src.scheduler.config import load_scheduler_config
        cfg_file = tmp_path / "s.yaml"
        cfg_file.write_text("trigger_time: '09:15'\nbackfill_max_days: 3\n", encoding="utf-8")
        cfg = load_scheduler_config(cfg_file)
        assert cfg.trigger_time == "09:15"
        assert cfg.backfill_max_days == 3

    def test_load_scheduler_config_defaults(self, tmp_path):
        from src.scheduler.config import load_scheduler_config
        # 指向不存在的文件 → 默认值
        cfg = load_scheduler_config(tmp_path / "nope.yaml")
        assert cfg.trigger_time == "16:00"
        assert cfg.backfill_max_days == 5

    def test_invalid_time_validation(self):
        from src.scheduler.config import SchedulerConfig
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            SchedulerConfig(trigger_time="25:00")
        with pytest.raises(ValidationError):
            SchedulerConfig(trigger_time="bad")
        with pytest.raises(ValidationError):
            SchedulerConfig(backfill_max_days=0)

    def test_hour_minute_properties(self):
        from src.scheduler.config import SchedulerConfig
        cfg = SchedulerConfig(trigger_time="09:30")
        assert cfg.hour == 9
        assert cfg.minute == 30
