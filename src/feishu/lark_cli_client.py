"""LarkCLIClient — 通过 subprocess 调用 lark-cli 实现 FeishuClient（plan §3 / Step6 §3.3）。

要点：
- _run() 显式传 PATH（launchd 兼容），超时 30s，日志脱敏
- _invoke() 带 tenacity 重试（仅重试 LarkCLITransientError）
- 错误码识别：1254104 降批、91403 告警、1254064 抛 SchemaError
- exit code 10 → SecurityError（高风险门禁，禁止自动加 --yes）
- health_check 检测 lark-cli 安装 / 凭证 / Base
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from loguru import logger
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.feishu.base_schema import FieldDef, TableSchema, load_schema_dir
from src.feishu.cards import FeishuCard
from src.feishu.client import FeishuClient
from src.feishu.config import FeishuConfig, dump_feishu_config
from src.feishu.error_codes import (
    DEGRADED_BATCH_SIZE,
    ERROR_CODE_MAP,
    BatchLimitExceeded,
    FeishuError,
    FeishuNotConfigured,
    LarkCLINotInstalled,
    LarkCLITransientError,
    PermissionDenied,
    SchemaError,
    SecurityError,
    classify_api_error,
)

# 显式 PATH（launchd 启动的进程 PATH 极简，不含 npm global bin）
EXPLICIT_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
DEFAULT_TIMEOUT = 30
LARK_CLI_BIN = "lark-cli"

# 命令行中需脱敏的参数 key（值不外泄到日志）
_SENSITIVE_KEYS = ("--app-secret", "--token", "--access-token", "--secret")

# 从响应文本中提取 JSON code 字段
_CODE_JSON_RE = re.compile(r'"code"\s*:\s*(\d+)')


def sanitize_cmd(cmd: list[str]) -> str:
    """脱敏命令用于日志：敏感参数值替换为 ***。

    处理两种形式：`--app-secret xxx` 与 `--app-secret=xxx`。
    """
    out: list[str] = []
    i = 0
    while i < len(cmd):
        part = cmd[i]
        # --key=value 形式
        matched_eq = False
        for key in _SENSITIVE_KEYS:
            if part.startswith(key + "="):
                out.append(f"{key}=***")
                matched_eq = True
                break
        if matched_eq:
            i += 1
            continue
        # --key value 形式
        if part in _SENSITIVE_KEYS and i + 1 < len(cmd):
            out.append(part)
            out.append("***")
            i += 2
            continue
        out.append(part)
        i += 1
    return " ".join(out)


def _parse_lark_json(stdout: str) -> Any:
    """从 lark-cli stdout 中解析首个 JSON 对象（容错：取含 { 的行）。"""
    if not stdout:
        return None
    text = stdout.strip()
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass
    # 尝试逐行找首个 JSON 对象
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
    return None


def _find_in_obj(obj: Any, key: str) -> Any:
    """递归查找对象中首个匹配 key 的值。"""
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_in_obj(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_in_obj(v, key)
            if r is not None:
                return r
    return None


class LarkCLIClient(FeishuClient):
    """通过 subprocess 调用 lark-cli 的 FeishuClient 实现。"""

    def __init__(
        self,
        config: FeishuConfig,
        *,
        cli_path: str = LARK_CLI_BIN,
        config_path: str | Path | None = None,
    ) -> None:
        self._config = config
        self._cli_path = cli_path
        self._config_path = str(config_path) if config_path else None
        self._retry_decorator = self._build_retry_decorator()
        # 推送限流时间戳
        self._last_send_ts: float = 0.0

    # ------------------------------------------------------------------
    # 诊断 / 前置检查（T00 / T01 / T06）
    # ------------------------------------------------------------------
    def _find_cli(self) -> str | None:
        """检测 lark-cli 是否安装。返回可执行路径或 None。"""
        # 优先按显式 PATH 查找（launchd 兼容）
        path_env = EXPLICIT_PATH + os.pathsep + os.environ.get("PATH", "")
        return shutil.which(self._cli_path, path=path_env)

    def _require_cli(self) -> None:
        if not self._find_cli():
            raise LarkCLINotInstalled(
                "lark-cli 未安装或不在 PATH。请运行：npm install -g @larksuite/cli"
            )

    def _require_credentials(self) -> None:
        if not self._config.app_id or not self._config.app_secret:
            raise FeishuNotConfigured(
                "缺少飞书凭证 app_id/app_secret。请设置 FEISHU_APP_ID / FEISHU_APP_SECRET "
                "或运行 `lark-cli config init`。"
            )

    def health_check(self) -> dict:
        """诊断：lark-cli / 凭证 / Base 三项状态 + 修复建议。"""
        result: dict[str, Any] = {
            "lark_cli": False,
            "token": False,
            "base": False,
            "advice": [],
        }
        # 1. lark-cli 是否安装
        if self._find_cli():
            result["lark_cli"] = True
        else:
            result["advice"].append(
                "lark-cli 未安装，运行：npm install -g @larksuite/cli"
            )
        # 2. 凭证就绪（token 由 lark-cli 自动管理，此处校验凭证是否足以获取 token）
        if self._config.app_id and self._config.app_secret:
            result["token"] = True
        else:
            result["advice"].append(
                "缺少 appId/appSecret，请设置环境变量 FEISHU_APP_ID / FEISHU_APP_SECRET"
            )
        # 3. Base 是否已创建
        if self._config.base_token:
            result["base"] = True
        else:
            result["advice"].append(
                "base_token 为空，运行 `python -m src.feishu init` 创建 Base"
            )
        return result

    # ------------------------------------------------------------------
    # subprocess 封装（T04 / T05 / T05b / T05c）
    # ------------------------------------------------------------------
    def _run(self, cmd: list[str], timeout: int = DEFAULT_TIMEOUT) -> subprocess.CompletedProcess:
        """显式传 PATH，超时控制，日志脱敏；exit 10 → SecurityError。"""
        env = {"PATH": EXPLICIT_PATH, **os.environ}
        logger.debug("lark-cli 调用：{}", sanitize_cmd(cmd))
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
        except FileNotFoundError as e:
            raise LarkCLINotInstalled(
                f"lark-cli 未安装或不在 PATH：{sanitize_cmd(cmd)}"
            ) from e
        except subprocess.TimeoutExpired as e:
            raise LarkCLITransientError(
                f"lark-cli 调用超时（{timeout}s）：{sanitize_cmd(cmd)}"
            ) from e

        # T05b：高风险门禁（exit 10）→ SecurityError，禁止自动加 --yes
        if result.returncode == 10:
            logger.error(
                "lark-cli 高风险门禁拦截（exit 10），命令骨架：{}",
                sanitize_cmd(cmd),
            )
            raise SecurityError(
                f"lark-cli 门禁拦截（高风险操作需用户确认）：{_gate_message(result)}"
            )
        return result

    def _detect_error(self, result: subprocess.CompletedProcess) -> FeishuError | None:
        """识别响应中的飞书 API 错误码；未知非零 exit 归为瞬时错误。"""
        blob = (result.stdout or "") + "\n" + (result.stderr or "")
        # 优先解析 JSON code 字段
        codes = [int(c) for c in _CODE_JSON_RE.findall(blob)]
        for code in codes:
            if code != 0 and code in ERROR_CODE_MAP:
                return classify_api_error(code, _extract_msg(blob))
        # 退一步：已知码直接出现在文本中
        for code in ERROR_CODE_MAP:
            if str(code) in blob:
                return classify_api_error(code, _extract_msg(blob))
        # 非零 exit 且无已知码 → 可重试瞬时错误
        if result.returncode != 0:
            return LarkCLITransientError(
                f"lark-cli 退出码 {result.returncode}：{(result.stderr or '').strip()}"
            )
        return None

    def _invoke(self, cmd: list[str], timeout: int = DEFAULT_TIMEOUT) -> str:
        """带重试的 lark-cli 调用；返回 stdout。失败抛对应 FeishuError 子类。

        仅 LarkCLITransientError 会重试；SecurityError / SchemaError /
        BatchLimitExceeded / PermissionDenied 等业务异常立即上抛。
        """

        @self._retry_decorator
        def _do() -> str:
            result = self._run(cmd, timeout=timeout)
            err = self._detect_error(result)
            if err is not None:
                raise err
            # 检测 lark-cli 更新提示（_notice.update）
            _maybe_notice_update(result.stdout)
            return result.stdout

        return _do()

    def _build_retry_decorator(self) -> Callable[[Callable[..., Any]], Any]:
        cfg = self._config.retry

        def _log_retry(state: RetryCallState) -> None:
            exc = state.outcome.exception() if state.outcome else None
            wait = state.next_action.sleep if state.next_action else 0
            logger.warning(
                "lark-cli 调用失败，第 {n}/{mx} 次重试（等待 {w:.1f}s）：{exc}",
                n=state.attempt_number,
                mx=cfg.max_attempts,
                w=wait,
                exc=repr(exc),
            )

        return retry(
            stop=stop_after_attempt(cfg.max_attempts),
            wait=wait_exponential(
                multiplier=cfg.backoff_base, exp_base=2, min=cfg.backoff_base
            ),
            retry=retry_if_exception_type(LarkCLITransientError),
            before_sleep=_log_retry,
            reraise=True,
        )

    # ------------------------------------------------------------------
    # 限流（FR-6）
    # ------------------------------------------------------------------
    def _throttle_send(self) -> None:
        """单聊推送 QPS 限流。"""
        qps = max(self._config.rate_limit.msg_qps, 1)
        min_interval = 1.0 / qps
        elapsed = time.time() - self._last_send_ts
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_send_ts = time.time()

    # ------------------------------------------------------------------
    # T08：init_base（创建 Base + 表 + 字段 + 视图）
    # ------------------------------------------------------------------
    def init_base(self, schema_dir: Path) -> str:
        self._require_cli()
        self._require_credentials()
        if self._config.base_token:
            logger.info(
                "Base 已存在（token={}...），跳过创建",
                _mask(self._config.base_token, 6),
            )
            return self._config.base_url

        schemas = load_schema_dir(schema_dir)
        logger.info("开始创建 Base，共 {} 张表", len(schemas))

        # 1. 创建 Base
        base_token = self._create_base()
        base_url = self._extract_base_url()
        self._config.base_token = base_token
        self._config.base_url = base_url
        logger.info("Base 创建成功：token={} url={}", _mask(base_token, 6), base_url)

        # 2. 逐表创建：表 + 字段 + 视图
        for schema in schemas:
            table_id = self._create_table(base_token, schema)
            self._create_fields(base_token, table_id, schema.fields)
            if schema.views:
                self._create_views(base_token, table_id, schema.views)
            # 写回 table_id 到配置
            tbl = self._config.table_by_name(schema.table_name)
            if tbl is not None:
                tbl.table_id = table_id
            logger.info("表 [{}] 创建完成 table_id={}", schema.table_name, table_id)

        # 3. 持久化配置
        if self._config_path:
            dump_feishu_config(self._config, self._config_path)
            logger.info("配置已写回：{}", self._config_path)

        return base_url

    def _create_base(self) -> str:
        cmd = [
            self._cli_path, "base", "+create",
            "--name", "TrandeAgent",
            "--folder-token", "",
            "--as", "user",
        ]
        stdout = self._invoke(cmd)
        token = _find_in_obj(_parse_lark_json(stdout), "app_token")
        if not token:
            token = _find_in_obj(_parse_lark_json(stdout), "token")
        if not token:
            raise LarkCLITransientError(f"创建 Base 未返回 token：{stdout.strip()}")
        return str(token)

    def _extract_base_url(self) -> str:
        url = self._config.base_url
        if url:
            return url
        # 若 lark-cli 返回了 url 则使用，否则按 token 拼占位
        return f"https://feishu.cn/base/{self._config.base_token}"

    def _create_table(self, base_token: str, schema: TableSchema) -> str:
        cmd = [
            self._cli_path, "base", "+table", "+create",
            "--app-token", base_token,
            "--name", schema.table_name,
            "--as", "user",
        ]
        stdout = self._invoke(cmd)
        table_id = _find_in_obj(_parse_lark_json(stdout), "table_id")
        if not table_id:
            raise LarkCLITransientError(
                f"创建表 [{schema.table_name}] 未返回 table_id：{stdout.strip()}"
            )
        return str(table_id)

    def _create_fields(self, base_token: str, table_id: str, fields: list[FieldDef]) -> None:
        for f in fields:
            cmd = [
                self._cli_path, "base", "+field", "+create",
                "--app-token", base_token,
                "--table-id", table_id,
                "--name", f.name,
                "--type", f.type,
                "--as", "user",
            ]
            if f.property:
                cmd += ["--property", json.dumps(f.property, ensure_ascii=False)]
            try:
                self._invoke(cmd)
            except PermissionDenied as e:
                logger.warning("无权限创建字段 [{}]（91403），跳过：{}", f.name, e)
            except FeishuError as e:
                logger.warning("创建字段 [{}] 失败，跳过：{}", f.name, e)

    def _create_views(self, base_token: str, table_id: str, views: list) -> None:
        for view in views:
            cmd = [
                self._cli_path, "base", "+view", "+create",
                "--app-token", base_token,
                "--table-id", table_id,
                "--name", view.name,
                "--as", "user",
            ]
            try:
                self._invoke(cmd)
            except FeishuError as e:
                logger.warning("创建视图 [{}] 失败，跳过：{}", view.name, e)

    # ------------------------------------------------------------------
    # T09：send_card（单聊推送）
    # ------------------------------------------------------------------
    def send_card(self, card: FeishuCard) -> str:
        self._require_cli()
        self._require_credentials()
        if not self._config.user_open_id:
            raise FeishuNotConfigured("缺少推送目标 user_open_id，请检查 config/feishu.yaml")

        payload = card.model_dump()
        content = json.dumps(payload, ensure_ascii=False)
        cmd = [
            self._cli_path, "im", "+messages-send",
            "--as", "bot",
            "--receive-id-type", "open_id",
            "--receive-id", self._config.user_open_id,
            "--msg-type", "interactive",
            "--content", content,
        ]
        self._throttle_send()
        stdout = self._invoke(cmd)
        msg_id = _find_in_obj(_parse_lark_json(stdout), "message_id")
        if not msg_id:
            raise LarkCLITransientError(f"推送未返回 message_id：{stdout.strip()}")
        logger.info("卡片推送成功 message_id={}", msg_id)
        return str(msg_id)

    # ------------------------------------------------------------------
    # T10：batch_upsert（批量写入，≤200/批，超限降批）
    # ------------------------------------------------------------------
    def batch_upsert(self, table_name: str, records: list[dict]) -> list[str]:
        self._require_cli()
        self._require_credentials()
        if not records:
            return []

        table_id = self._resolve_table_id(table_name)
        base_token = self._config.base_token
        batch_size = self._config.rate_limit.base_batch_size
        interval = self._config.rate_limit.base_batch_interval_sec

        record_ids: list[str] = []
        i = 0
        n = len(records)
        while i < n:
            batch = records[i : i + batch_size]
            try:
                ids = self._upsert_batch(base_token, table_id, batch)
                record_ids.extend(ids)
            except BatchLimitExceeded:
                # 1254104：自动降批到 100 重试（FR-6 / T05）
                if batch_size > DEGRADED_BATCH_SIZE:
                    batch_size = DEGRADED_BATCH_SIZE
                    logger.warning(
                        "批量写入 [{}] 超限（1254104），降批到 {} 重试",
                        table_name, batch_size,
                    )
                    continue
                raise
            except PermissionDenied as e:
                # 91403：告警不中断，跳过本批继续后续
                logger.warning(
                    "无权限写入 [{}]（91403），跳过本批 {} 条：{}",
                    table_name, len(batch), e,
                )
            i += len(batch)
            if i < n:
                time.sleep(interval)
        logger.info(
            "批量写入 [{}] 完成：共 {} 条，返回 {} 个 record_id",
            table_name, n, len(record_ids),
        )
        return record_ids

    def _upsert_batch(self, base_token: str, table_id: str, batch: list[dict]) -> list[str]:
        records_json = json.dumps(batch, ensure_ascii=False)
        cmd = [
            self._cli_path, "base", "+record", "+batch-create",
            "--app-token", base_token,
            "--table-id", table_id,
            "--records", records_json,
            "--as", "user",
        ]
        stdout = self._invoke(cmd)
        obj = _parse_lark_json(stdout)
        ids = _find_in_obj(obj, "record_ids")
        if ids is None:
            # 单条记录场景可能返回 record_id
            single = _find_in_obj(obj, "record_id")
            ids = [single] if single else []
        return [str(x) for x in ids]

    def _resolve_table_id(self, table_name: str) -> str:
        tbl = self._config.table_by_name(table_name)
        if tbl is None:
            raise FeishuNotConfigured(f"配置中未找到表 [{table_name}]")
        if not tbl.table_id:
            raise FeishuNotConfigured(
                f"表 [{table_name}] 尚未初始化 table_id，请先运行 feishu init"
            )
        return tbl.table_id

    # ------------------------------------------------------------------
    # T11：query_records + update_views
    # ------------------------------------------------------------------
    def query_records(self, table_name: str, filter: dict | None = None) -> list[dict]:
        self._require_cli()
        self._require_credentials()
        table_id = self._resolve_table_id(table_name)
        base_token = self._config.base_token

        cmd = [
            self._cli_path, "base", "+record", "+search",
            "--app-token", base_token,
            "--table-id", table_id,
            "--as", "user",
        ]
        if filter:
            cmd += ["--filter", json.dumps(filter, ensure_ascii=False)]
        stdout = self._invoke(cmd)
        obj = _parse_lark_json(stdout)
        items = _find_in_obj(obj, "items")
        if items is None:
            items = _find_in_obj(obj, "records")
        if items is None:
            items = obj if isinstance(obj, list) else []
        return items if isinstance(items, list) else []

    def update_views(self, table_name: str, views: list[dict]) -> None:
        self._require_cli()
        self._require_credentials()
        table_id = self._resolve_table_id(table_name)
        base_token = self._config.base_token

        for view in views:
            name = view.get("name", "")
            cmd = [
                self._cli_path, "base", "+view", "+update",
                "--app-token", base_token,
                "--table-id", table_id,
                "--name", name,
                "--as", "user",
            ]
            if view.get("filter"):
                cmd += ["--filter", json.dumps(view["filter"], ensure_ascii=False)]
            if view.get("sort"):
                cmd += ["--sort", json.dumps(view["sort"], ensure_ascii=False)]
            if view.get("group"):
                cmd += ["--group", json.dumps(view["group"], ensure_ascii=False)]
            try:
                self._invoke(cmd)
            except PermissionDenied as e:
                logger.warning("无权限更新视图 [{}]（91403），跳过：{}", name, e)
            logger.info("视图 [{}] 已更新", name)


# ----------------------------------------------------------------------
# 模块级辅助函数
# ----------------------------------------------------------------------
def _gate_message(result: subprocess.CompletedProcess) -> str:
    """解析 exit 10 的 stderr envelope 提取可读信息（脱敏）。"""
    try:
        obj = _parse_lark_json(result.stderr or "")
        err = _find_in_obj(obj, "error") or _find_in_obj(obj, "type")
        if err:
            return str(err)
    except Exception:  # noqa: BLE001
        pass
    return _mask((result.stderr or "").strip(), 200)


def _extract_msg(blob: str) -> str:
    """从响应文本中提取 msg/message 字段（脱敏后返回）。"""
    obj = _parse_lark_json(blob)
    msg = _find_in_obj(obj, "msg") or _find_in_obj(obj, "message")
    return _mask(str(msg), 200) if msg else _mask(blob.strip(), 200)


def _maybe_notice_update(stdout: str) -> None:
    """检测 lark-cli 响应中的 _notice.update 字段，提示用户更新（FR-7）。"""
    if "_notice" not in (stdout or ""):
        return
    obj = _parse_lark_json(stdout)
    notice = _find_in_obj(obj, "update") if isinstance(obj, dict) else None
    if notice:
        logger.warning(
            "检测到 lark-cli 版本更新提示：{}. 建议运行："
            "npm update -g @larksuite/cli && npx skills add larksuite/cli -g -y",
            notice,
        )


def _mask(text: str, keep: int = 6) -> str:
    """脱敏：保留前 keep 位，其余替换为 ***。用于 token/secret 日志输出。"""
    if not text:
        return ""
    if len(text) <= keep:
        return text[:1] + "***"
    return text[:keep] + "***"
