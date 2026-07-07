"""T04/T05/T05b/T05c/T06/T08-T11: LarkCLIClient 单元测试（mock subprocess）。

全部用 mock subprocess，不依赖真实 lark-cli。
"""
from __future__ import annotations

import json
import subprocess

import pytest

from src.feishu.cards import CardAction, CardElement, FeishuCard
from src.feishu.error_codes import (
    BatchLimitExceeded,
    FeishuNotConfigured,
    LarkCLINotInstalled,
    LarkCLITransientError,
    PermissionDenied,
    SchemaError,
    SecurityError,
)
from src.feishu.lark_cli_client import (
    LarkCLIClient,
    _find_in_obj,
    _mask,
    _parse_lark_json,
    sanitize_cmd,
)


# ----------------------------------------------------------------------
# 模块级辅助函数测试（T05c 脱敏）
# ----------------------------------------------------------------------
class TestSanitizeCmd:
    def test_mask_space_form(self):
        cmd = ["lark-cli", "--app-secret", "supersecret", "--as", "bot"]
        out = sanitize_cmd(cmd)
        assert "supersecret" not in out
        assert "--app-secret ***" in out

    def test_mask_equals_form(self):
        cmd = ["lark-cli", "--app-secret=supersecret", "--as", "bot"]
        out = sanitize_cmd(cmd)
        assert "supersecret" not in out
        assert "--app-secret=***" in out

    def test_mask_token(self):
        cmd = ["lark-cli", "--token", "t-abc123", "do"]
        assert "t-abc123" not in sanitize_cmd(cmd)

    def test_no_secret_unchanged(self):
        cmd = ["lark-cli", "base", "+create", "--name", "TrandeAgent"]
        out = sanitize_cmd(cmd)
        assert "TrandeAgent" in out

    def test_secret_as_last_arg(self):
        # 末尾是敏感 key 但无值 → 不越界
        cmd = ["lark-cli", "--app-secret"]
        out = sanitize_cmd(cmd)
        assert "--app-secret" in out


class TestMask:
    def test_long_string_masked(self):
        assert _mask("basTokenVeryLong123", 6) == "basTok***"

    def test_short_string(self):
        assert _mask("ab") == "a***"

    def test_empty(self):
        assert _mask("") == ""


class TestParseJson:
    def test_parse_plain_json(self):
        assert _parse_lark_json('{"code":0,"data":{"id":"x"}}')["code"] == 0

    def test_parse_json_in_line(self):
        stdout = "some log line\n" + json.dumps({"message_id": "om123"})
        obj = _parse_lark_json(stdout)
        assert _find_in_obj(obj, "message_id") == "om123"

    def test_parse_empty(self):
        assert _parse_lark_json("") is None
        assert _parse_lark_json("not json at all") is None

    def test_find_in_obj_nested(self):
        obj = {"data": {"items": [{"record_id": "rec1"}]}}
        assert _find_in_obj(obj, "record_id") == "rec1"


# ----------------------------------------------------------------------
# _run / _detect_error / _invoke 测试（T04 / T05 / T05b）
# ----------------------------------------------------------------------
class TestRunAndInvoke:
    def test_run_exit10_raises_security(self, client, make_proc, monkeypatch):
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda *a, **k: make_proc(stderr='{"error":{"type":"confirmation_required"}}', returncode=10),
        )
        with pytest.raises(SecurityError):
            client._run(["lark-cli", "x"])

    def test_run_filenotfound_raises_not_installed(self, client, monkeypatch):
        def _raise(*a, **k):
            raise FileNotFoundError("no binary")

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", _raise)
        with pytest.raises(LarkCLINotInstalled):
            client._run(["lark-cli", "x"])

    def test_run_timeout_raises_transient(self, client, monkeypatch):
        def _raise(*a, **k):
            raise subprocess.TimeoutExpired(cmd="lark-cli", timeout=30)

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", _raise)
        with pytest.raises(LarkCLITransientError):
            client._run(["lark-cli", "x"])

    def test_detect_1254104_batch_limit(self, client, make_proc):
        result = make_proc(stdout='{"code":1254104,"msg":"too many"}')
        err = client._detect_error(result)
        assert isinstance(err, BatchLimitExceeded)

    def test_detect_91403_permission(self, client, make_proc):
        result = make_proc(stderr='{"code":91403,"msg":"forbidden"}', returncode=1)
        err = client._detect_error(result)
        assert isinstance(err, PermissionDenied)

    def test_detect_1254064_schema(self, client, make_proc):
        result = make_proc(stdout='{"code":1254064,"msg":"bad date"}')
        err = client._detect_error(result)
        assert isinstance(err, SchemaError)

    def test_detect_unknown_nonzero_transient(self, client, make_proc):
        result = make_proc(stderr="boom", returncode=2)
        err = client._detect_error(result)
        assert isinstance(err, LarkCLITransientError)

    def test_detect_success_none(self, client, make_proc):
        result = make_proc(stdout='{"code":0,"data":{}}')
        assert client._detect_error(result) is None

    def test_invoke_retries_transient_then_succeeds(self, client, make_proc, monkeypatch):
        calls = {"n": 0}

        def runner(cmd, **kw):
            calls["n"] += 1
            if calls["n"] < 3:
                return make_proc(stderr="temp fail", returncode=2)
            return make_proc(stdout='{"code":0,"message_id":"om_ok"}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        out = client._invoke(["lark-cli", "x"])
        assert "om_ok" in out
        assert calls["n"] == 3

    def test_invoke_no_retry_on_schema_error(self, client, make_proc, monkeypatch):
        calls = {"n": 0}

        def runner(cmd, **kw):
            calls["n"] += 1
            return make_proc(stdout='{"code":1254064,"msg":"bad date"}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        with pytest.raises(SchemaError):
            client._invoke(["lark-cli", "x"])
        assert calls["n"] == 1  # 不重试

    def test_invoke_no_retry_on_security(self, client, make_proc, monkeypatch):
        calls = {"n": 0}

        def runner(cmd, **kw):
            calls["n"] += 1
            return make_proc(returncode=10, stderr='{"error":{"type":"confirmation_required"}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        with pytest.raises(SecurityError):
            client._invoke(["lark-cli", "x"])
        assert calls["n"] == 1

    def test_invoke_exhausts_retries_raises_transient(self, client, make_proc, monkeypatch):
        def runner(cmd, **kw):
            return make_proc(stderr="always fail", returncode=3)

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        with pytest.raises(LarkCLITransientError):
            client._invoke(["lark-cli", "x"])

    def test_invoke_detects_update_notice(self, client, make_proc, monkeypatch):
        # FR-7：响应含 _notice.update 时输出更新提示日志
        from loguru import logger

        stdout = '{"code":0,"data":{},"_notice":{"update":"1.2.0 available"}}'
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda cmd, **kw: make_proc(stdout=stdout),
        )
        sink = []
        handle_id = logger.add(sink.append, level="WARNING", format="{message}")
        try:
            client._invoke(["lark-cli", "x"])
        finally:
            logger.remove(handle_id)
        captured = "\n".join(sink)
        assert "1.2.0 available" in captured
        assert "npm update" in captured




# ----------------------------------------------------------------------
# T06：health_check
# ----------------------------------------------------------------------
class TestHealthCheck:
    def test_all_healthy(self, client):
        # client fixture 已 mock cli + 配置了凭证 + base_token
        result = client.health_check()
        assert result["lark_cli"] is True
        assert result["token"] is True
        assert result["base"] is True
        assert result["advice"] == []

    def test_lark_cli_not_installed(self, fake_config, monkeypatch):
        c = LarkCLIClient(fake_config)
        monkeypatch.setattr(c, "_find_cli", lambda: None)  # 未安装
        result = c.health_check()
        assert result["lark_cli"] is False
        assert any("npm install" in a for a in result["advice"])

    def test_missing_credentials(self, monkeypatch):
        from src.feishu.config import FeishuConfig

        c = LarkCLIClient(FeishuConfig(app_id="", app_secret="", base_token="basX"))
        monkeypatch.setattr(c, "_find_cli", lambda: "/fake/lark-cli")
        result = c.health_check()
        assert result["token"] is False
        assert any("FEISHU_APP_ID" in a for a in result["advice"])

    def test_missing_base(self, monkeypatch):
        from src.feishu.config import FeishuConfig

        c = LarkCLIClient(FeishuConfig(app_id="a", app_secret="b", base_token=""))
        monkeypatch.setattr(c, "_find_cli", lambda: "/fake/lark-cli")
        result = c.health_check()
        assert result["base"] is False
        assert any("base_token" in a for a in result["advice"])

    def test_require_cli_raises_when_not_installed(self, fake_config, monkeypatch):
        c = LarkCLIClient(fake_config)
        monkeypatch.setattr(c, "_find_cli", lambda: None)
        with pytest.raises(LarkCLINotInstalled):
            c._require_cli()


# ----------------------------------------------------------------------
# T09：send_card
# ----------------------------------------------------------------------
class TestSendCard:
    def _card(self):
        return FeishuCard(
            header={"template": "blue", "title": {"content": "测试"}},
            elements=[
                CardElement(tag="markdown", content="hello"),
                CardElement(
                    tag="action",
                    actions=[CardAction(text={"content": "go"}, open_url="https://x").model_dump()],
                ),
            ],
        )

    def test_send_card_success(self, client, make_proc, monkeypatch):
        captured = {}

        def runner(cmd, **kw):
            captured["cmd"] = cmd
            return make_proc(stdout='{"code":0,"data":{"message_id":"om_send_123"}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        msg_id = client.send_card(self._card())
        assert msg_id == "om_send_123"
        # 验证命令骨架（不校验完整顺序，只校验关键参数）
        joined = " ".join(captured["cmd"])
        assert "im" in captured["cmd"]
        assert "+messages-send" in captured["cmd"]
        assert "--msg-type" in captured["cmd"] and "interactive" in captured["cmd"]
        assert "--as" in captured["cmd"] and "bot" in captured["cmd"]
        assert "ou_testuser0001" in joined

    def test_send_card_missing_open_id(self, monkeypatch, fake_config):
        from src.feishu.config import FeishuConfig

        cfg = FeishuConfig(
            app_id="a", app_secret="b", user_open_id="", base_token="basX"
        )
        c = LarkCLIClient(cfg)
        monkeypatch.setattr(c, "_find_cli", lambda: "/fake/lark-cli")
        with pytest.raises(FeishuNotConfigured):
            c.send_card(self._card())

    def test_send_card_missing_message_id(self, client, make_proc, monkeypatch):
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda cmd, **kw: make_proc(stdout='{"code":0}'),
        )
        with pytest.raises(LarkCLITransientError):
            client.send_card(self._card())


# ----------------------------------------------------------------------
# T10：batch_upsert
# ----------------------------------------------------------------------
class TestBatchUpsert:
    def test_single_batch_success(self, client, make_proc, monkeypatch):
        captured = {}

        def runner(cmd, **kw):
            captured["cmd"] = cmd
            return make_proc(stdout='{"code":0,"data":{"record_ids":["rec1","rec2"]}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        ids = client.batch_upsert("基金池", [{"基金代码": "000001"}, {"基金代码": "161725"}])
        assert ids == ["rec1", "rec2"]
        assert "+batch-create" in captured["cmd"]

    def test_empty_records_returns_empty(self, client):
        assert client.batch_upsert("基金池", []) == []

    def test_multi_batch_split(self, client, make_proc, monkeypatch):
        # batch_size=200，250 条 → 2 批（200 + 50）
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            return make_proc(stdout='{"code":0,"data":{"record_ids":["r"]}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        records = [{"基金代码": str(i)} for i in range(250)]
        client.batch_upsert("基金池", records)
        assert len(calls) == 2

    def test_1254104_degrade_batch(self, client, make_proc, monkeypatch):
        # 用较小配置便于验证降批：batch_size=200，但首响应 1254104
        calls = {"n": 0}

        def runner(cmd, **kw):
            calls["n"] += 1
            # 第一次返回超限，后续成功
            if calls["n"] == 1:
                return make_proc(stdout='{"code":1254104,"msg":"limit"}')
            return make_proc(stdout='{"code":0,"data":{"record_ids":["rec"]}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        # 给 100 条 → 降批到 100 后单批重试成功
        records = [{"基金代码": str(i)} for i in range(100)]
        ids = client.batch_upsert("基金池", records)
        assert "rec" in ids

    def test_91403_skip_batch_no_interrupt(self, client, make_proc, monkeypatch):
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda cmd, **kw: make_proc(stderr='{"code":91403}', returncode=1),
        )
        # 无权限告警，不抛异常，返回空 ids
        ids = client.batch_upsert("基金池", [{"基金代码": "000001"}])
        assert ids == []

    def test_unknown_table_raises(self, client):
        with pytest.raises(FeishuNotConfigured):
            client.batch_upsert("不存在表", [{"x": 1}])

    def test_table_without_id_raises(self, monkeypatch, fake_config):
        from src.feishu.config import FeishuConfig, TableConfig

        cfg = FeishuConfig(
            app_id="a", app_secret="b", base_token="basX",
            tables=[TableConfig(name="基金池", table_id="", fields_file="x.yaml")],
        )
        c = LarkCLIClient(cfg)
        monkeypatch.setattr(c, "_find_cli", lambda: "/fake/lark-cli")
        with pytest.raises(FeishuNotConfigured):
            c.batch_upsert("基金池", [{"x": 1}])


# ----------------------------------------------------------------------
# T11：query_records + update_views
# ----------------------------------------------------------------------
class TestQueryAndUpdateViews:
    def test_query_records_success(self, client, make_proc, monkeypatch):
        captured = {}

        def runner(cmd, **kw):
            captured["cmd"] = cmd
            return make_proc(
                stdout='{"code":0,"data":{"items":[{"基金代码":"000001"},{"基金代码":"161725"}]}}'
            )

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        rows = client.query_records("基金池")
        assert len(rows) == 2
        assert rows[0]["基金代码"] == "000001"
        assert "+search" in captured["cmd"]

    def test_query_records_with_filter(self, client, make_proc, monkeypatch):
        captured = {}

        def runner(cmd, **kw):
            captured["cmd"] = cmd
            return make_proc(stdout='{"code":0,"data":{"items":[]}}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        client.query_records("基金池", filter={"评级": 5})
        joined = " ".join(captured["cmd"])
        assert "--filter" in captured["cmd"]
        assert "评级" in joined

    def test_query_records_fallback_records_key(self, client, make_proc, monkeypatch):
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda cmd, **kw: make_proc(stdout='{"records":[{"a":1}]}'),
        )
        rows = client.query_records("基金池")
        assert rows == [{"a": 1}]

    def test_update_views_success(self, client, make_proc, monkeypatch):
        calls = []

        def runner(cmd, **kw):
            calls.append(cmd)
            return make_proc(stdout='{"code":0}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        client.update_views(
            "基金池",
            [
                {"name": "今日候选", "filter": {"评级": "desc"}, "sort": {"评级": "desc"}},
                {"name": "观察池"},
            ],
        )
        assert len(calls) == 2
        assert "+view" in calls[0] and "+update" in calls[0]

    def test_update_views_permission_skip(self, client, make_proc, monkeypatch):
        monkeypatch.setattr(
            "src.feishu.lark_cli_client.subprocess.run",
            lambda cmd, **kw: make_proc(stderr='{"code":91403}', returncode=1),
        )
        # 不抛异常，仅告警
        client.update_views("基金池", [{"name": "v1"}])


# ----------------------------------------------------------------------
# T08：init_base
# ----------------------------------------------------------------------
class TestInitBase:
    def test_init_base_full(self, client, make_proc, monkeypatch, tmp_path):
        from tests.feishu.conftest import REAL_SCHEMA_DIR

        client._config.base_token = ""
        client._config.base_url = ""
        for t in client._config.tables:
            t.table_id = ""
        client._config_path = str(tmp_path / "feishu_out.yaml")

        def runner(cmd, **kw):
            if "+table" in cmd and "+create" in cmd and "+field" not in cmd and "+view" not in cmd:
                return make_proc(stdout='{"code":0,"data":{"table_id":"tblNEW"}}')
            if cmd[:3] == ["lark-cli", "base", "+create"] or (
                "base" in cmd and "+create" in cmd and "+table" not in cmd
                and "+field" not in cmd and "+view" not in cmd
            ):
                return make_proc(stdout='{"code":0,"data":{"app_token":"basNEW","url":"https://feishu.cn/base/basNEW"}}')
            return make_proc(stdout='{"code":0}')

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        url = client.init_base(REAL_SCHEMA_DIR)
        assert "basNEW" in client._config.base_token
        # table_id 已写回
        assert client._config.table_by_name("基金池").table_id == "tblNEW"
        # 配置已持久化
        assert (tmp_path / "feishu_out.yaml").exists()

    def test_init_skip_when_token_exists(self, client, monkeypatch):
        # base_token 已存在 → 直接返回 url，不调用 subprocess
        called = {"n": 0}

        def runner(cmd, **kw):
            called["n"] += 1
            return make_proc()

        monkeypatch.setattr("src.feishu.lark_cli_client.subprocess.run", runner)
        url = client.init_base(REAL_SCHEMA_DIR_PLACEHOLDER)
        assert called["n"] == 0


REAL_SCHEMA_DIR_PLACEHOLDER = __import__("pathlib").Path(__file__).resolve().parent.parent.parent / "config" / "feishu_base_schemas"


class TestInitBaseRequires:
    def test_init_requires_cli(self, fake_config, monkeypatch):
        c = LarkCLIClient(fake_config)
        monkeypatch.setattr(c, "_find_cli", lambda: None)
        with pytest.raises(LarkCLINotInstalled):
            c.init_base(REAL_SCHEMA_DIR_PLACEHOLDER)

    def test_init_requires_credentials(self, monkeypatch):
        from src.feishu.config import FeishuConfig

        c = LarkCLIClient(FeishuConfig(app_id="", app_secret=""))
        monkeypatch.setattr(c, "_find_cli", lambda: "/fake/lark-cli")
        with pytest.raises(FeishuNotConfigured):
            c.init_base(REAL_SCHEMA_DIR_PLACEHOLDER)


# ----------------------------------------------------------------------
# 抽象接口测试
# ----------------------------------------------------------------------
class TestAbstract:
    def test_cannot_instantiate_abstract(self):
        from src.feishu.client import FeishuClient

        with pytest.raises(TypeError):
            FeishuClient()  # type: ignore[abstract]

    def test_larkcli_is_subclass(self):
        from src.feishu.client import FeishuClient

        assert issubclass(LarkCLIClient, FeishuClient)
