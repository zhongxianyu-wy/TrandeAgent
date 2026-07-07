"""T12: 配置加载与环境变量校验测试。"""
from __future__ import annotations

import pytest

from src.feishu.config import (
    FeishuConfig,
    dump_feishu_config,
    load_feishu_config,
    validate_credentials,
)
from src.feishu.error_codes import FeishuNotConfigured


def _write_yaml(tmp_path, text):
    p = tmp_path / "feishu.yaml"
    p.write_text(text, encoding="utf-8")
    return p


class TestConfigLoad:
    def test_env_var_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("FEISHU_APP_ID", "cli_expanded")
        monkeypatch.setenv("FEISHU_APP_SECRET", "secret_expanded")
        p = _write_yaml(
            tmp_path,
            "app_id: ${FEISHU_APP_ID}\napp_secret: ${FEISHU_APP_SECRET}\nuser_open_id: 'ou_x'\n",
        )
        cfg = load_feishu_config(p, strict=False)
        assert cfg.app_id == "cli_expanded"
        assert cfg.app_secret == "secret_expanded"

    def test_unset_env_kept_as_placeholder(self, tmp_path, monkeypatch):
        monkeypatch.delenv("FEISHU_NOT_SET", raising=False)
        p = _write_yaml(tmp_path, "app_id: ${FEISHU_NOT_SET}\n")
        cfg = load_feishu_config(p, strict=False)
        assert cfg.app_id == "${FEISHU_NOT_SET}"

    def test_strict_raises_when_missing_app_id(self, tmp_path):
        p = _write_yaml(tmp_path, "app_secret: 's'\n")
        with pytest.raises(FeishuNotConfigured) as exc:
            load_feishu_config(p, strict=True)
        assert "app_id" in str(exc.value)

    def test_strict_raises_when_missing_both(self, tmp_path):
        p = _write_yaml(tmp_path, "user_open_id: 'ou_x'\n")
        with pytest.raises(FeishuNotConfigured):
            load_feishu_config(p, strict=True)

    def test_strict_false_no_raise(self, tmp_path):
        p = _write_yaml(tmp_path, "user_open_id: 'ou_x'\n")
        cfg = load_feishu_config(p, strict=False)
        assert cfg.app_id == ""

    def test_validate_credentials_ok(self):
        cfg = FeishuConfig(app_id="a", app_secret="b")
        validate_credentials(cfg)  # no raise

    def test_validate_credentials_missing(self):
        cfg = FeishuConfig(app_id="", app_secret="b")
        with pytest.raises(FeishuNotConfigured):
            validate_credentials(cfg)

    def test_rate_limit_and_retry_defaults(self, tmp_path):
        p = _write_yaml(
            tmp_path,
            "app_id: 'a'\napp_secret: 'b'\nrate_limit:\n  base_batch_size: 50\n",
        )
        cfg = load_feishu_config(p)
        assert cfg.rate_limit.base_batch_size == 50
        assert cfg.rate_limit.msg_qps == 5  # 默认
        assert cfg.retry.max_attempts == 3  # 默认

    def test_table_by_name(self):
        from src.feishu.config import TableConfig

        cfg = FeishuConfig(
            tables=[
                TableConfig(name="基金池", fields_file="a.yaml"),
                TableConfig(name="信号", fields_file="b.yaml"),
            ]
        )
        assert cfg.table_by_name("信号").fields_file == "b.yaml"
        assert cfg.table_by_name("不存在") is None

    def test_dump_and_reload_roundtrip(self, tmp_path):
        p = tmp_path / "feishu.yaml"
        cfg = FeishuConfig(
            app_id="cli_dump",
            app_secret="secret_dump",
            base_token="basX",
            base_url="https://x/base",
        )
        dump_feishu_config(cfg, p)
        reloaded = load_feishu_config(p)
        assert reloaded.base_token == "basX"
        assert reloaded.app_id == "cli_dump"

    def test_load_missing_file_uses_defaults(self, tmp_path, monkeypatch):
        # 指定不存在的文件 → 默认配置（strict=False）
        cfg = load_feishu_config(tmp_path / "nope.yaml", strict=False)
        assert cfg.rate_limit.base_batch_size == 200
