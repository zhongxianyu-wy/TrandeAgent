"""pytest 全局 fixtures（Feature #2 feishu-io）。"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src.feishu.config import FeishuConfig, RateLimitConfig, RetryConfig, TableConfig

# 项目根（用于定位真实 config 目录）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_SCHEMA_DIR = PROJECT_ROOT / "config" / "feishu_base_schemas"
REAL_FEISHU_YAML = PROJECT_ROOT / "config" / "feishu.yaml"


def make_config(
    *,
    app_id: str = "cli_test_app",
    app_secret: str = "secret_test_value",
    user_open_id: str = "ou_testuser0001",
    base_token: str = "bas0000000000000001",
    base_url: str = "https://feishu.cn/base/bas0000000000000001",
) -> FeishuConfig:
    """构造一份测试用 FeishuConfig（含 4 张表的 table_id）。"""
    return FeishuConfig(
        app_id=app_id,
        app_secret=app_secret,
        user_open_id=user_open_id,
        base_token=base_token,
        base_url=base_url,
        tables=[
            TableConfig(name="基金池", table_id="tblPool001", fields_file="fund_pool.yaml"),
            TableConfig(name="信号", table_id="tblSignal01", fields_file="signals.yaml"),
            TableConfig(name="策略竞技场", table_id="tblArena01", fields_file="arena.yaml"),
            TableConfig(name="复盘", table_id="tblReview01", fields_file="review.yaml"),
        ],
        rate_limit=RateLimitConfig(msg_qps=100, base_batch_size=200, base_batch_interval_sec=0.0),
        retry=RetryConfig(max_attempts=3, backoff_base=0.0),
    )


@pytest.fixture
def fake_config() -> FeishuConfig:
    return make_config()


@pytest.fixture
def client(fake_config, monkeypatch):
    """构造一个 LarkCLIClient，_find_cli 已 mock 为已安装。"""
    from src.feishu.lark_cli_client import LarkCLIClient

    c = LarkCLIClient(fake_config)
    monkeypatch.setattr(c, "_find_cli", lambda: "/fake/path/lark-cli")
    return c


def proc(stdout: str = "", stderr: str = "", returncode: int = 0) -> subprocess.CompletedProcess:
    """构造 CompletedProcess 用于 mock subprocess.run。"""
    return subprocess.CompletedProcess(
        args=["lark-cli"], returncode=returncode, stdout=stdout, stderr=stderr
    )


@pytest.fixture
def make_proc():
    return proc


def patch_run(monkeypatch, runner):
    """把 lark_cli_client.subprocess.run 替换为 runner（callable(cmd, **kw)）。"""
    monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
    return runner
