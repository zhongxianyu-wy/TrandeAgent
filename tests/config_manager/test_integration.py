"""T12：集成测试 —— save → analyze_impact → rollback 端到端。

覆盖 plan §5 测试策略中的集成场景，使用 tmp_path 初始化临时 git 仓库。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.config_manager.manager import DefaultConfigManager
from src.config_manager.schema import ArenaSection

from tests.config_manager.conftest import make_config, make_screener_rule, make_signal_rule


class TestSaveImpactRollback:
    """端到端：保存 v1 → 保存 v2 → 分析影响 → 回滚到 v1。"""

    def test_full_lifecycle(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)

        # v1: 初始配置
        v1 = make_config(
            pool=["001", "002"],
            screener=[
                make_screener_rule(name="return_top33", value=0.33),
                make_screener_rule(name="scale", field="l1_basic.scale", op="between", value=[2.0, 50.0]),
            ],
            signals=[make_signal_rule(name="均线金叉", threshold=0)],
            arena=ArenaSection(strategy_count=100),
        )
        h1 = mgr.save_with_commit(v1, "v1: 初始配置")

        # v2: 修改配置
        v2 = make_config(
            pool=["001", "002", "003"],
            screener=[
                make_screener_rule(name="return_top33", value=0.33),
                make_screener_rule(name="scale", field="l1_basic.scale", op="between", value=[2.0, 100.0]),
                make_screener_rule(name="sharpe", value=0.25),
            ],
            signals=[
                make_signal_rule(name="均线金叉", threshold=0),
                make_signal_rule(name="RSI超卖", indicator="rsi", threshold=30, weight=0.8),
            ],
            arena=ArenaSection(strategy_count=200),
        )
        h2 = mgr.save_with_commit(v2, "v2: 放宽规模+加信号")

        # 分析 v1 -> v2 影响
        impacts = mgr.analyze_impact(v1, v2)
        types = [i.change_type for i in impacts]
        assert "pool" in types
        assert "screener" in types
        assert "signal" in types
        assert "arena" in types

        # arena 应要求重跑
        arena_impact = next(i for i in impacts if i.change_type == "arena")
        assert arena_impact.requires_backtest_rerun is True

        # git 历史
        entries = mgr.log()
        assert len(entries) == 2
        assert "v2" in entries[0]["message"]

        # 回滚到 v1
        restored = mgr.rollback(h1)
        assert restored.observation_pool == ["001", "002"]
        assert len(restored.screener_rules) == 2
        assert "sharpe" not in [r.name for r in restored.screener_rules]

    def test_rollback_to_head_when_no_change(self, git_repo):
        """保存同一配置两次，回滚到 HEAD~1 应恢复相同内容。"""
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        cfg = make_config(pool=["001"])
        mgr.save_with_commit(cfg, "first")

        # 修改后保存
        cfg2 = make_config(pool=["001", "002"])
        mgr.save_with_commit(cfg2, "second")
        h1 = mgr.log()[-1]["hash"]  # 第一个 commit

        restored = mgr.rollback(h1)
        assert restored.observation_pool == ["001"]


class TestValidateBeforeSave:
    """保存前校验流程。"""

    def test_validate_then_save(self, git_repo):
        cfg_path = git_repo / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)

        # 先写一个有效配置
        from tests.config_manager.conftest import VALID_YAML

        cfg_path.write_text(VALID_YAML, encoding="utf-8")
        issues = mgr.validate(cfg_path.read_text(encoding="utf-8"))
        assert issues == []

        # 校验通过后正式保存
        cfg = mgr.load()
        mgr.save_with_commit(cfg, "validated config")
        assert len(mgr.log()) == 1

    def test_catch_invalid_before_save(self, tmp_path):
        cfg_path = tmp_path / "strategies.yaml"
        mgr = DefaultConfigManager(cfg_path)
        bad_yaml = (
            "observation_pool:\n"
            "  - '001'\n"
            "screener_rules:\n"
            "  - name: r1\n"
            "    field: sharpe\n"
            "    op: bad_op\n"
            "    value: 1.0\n"
            "signal_rules: []\n"
        )
        issues = mgr.validate(bad_yaml)
        assert len(issues) >= 1
        # 有错误时不应保存
        assert not cfg_path.exists()


class TestEnvVarIntegration:
    """环境变量替换端到端。"""

    def test_load_with_env_var(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FUND_A", "888888")
        cfg_path = tmp_path / "cfg.yaml"
        cfg_path.write_text(
            "observation_pool:\n  - ${FUND_A}\n"
            "screener_rules: []\nsignal_rules: []\n",
            encoding="utf-8",
        )
        mgr = DefaultConfigManager(cfg_path)
        cfg = mgr.load()
        assert "888888" in cfg.observation_pool
