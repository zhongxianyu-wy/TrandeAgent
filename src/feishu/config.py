"""飞书配置加载与环境变量校验（plan §2.1 / T12 / AC-5）。

从 config/feishu.yaml 加载，`${VAR}` 形式的环境变量自动替换；
缺 appId/appSecret 时抛 FeishuNotConfigured，提示运行 lark-cli config init。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import BaseModel, Field

from src.feishu.error_codes import FeishuNotConfigured

# ${VAR} 或 $VAR 形式的环境变量占位符
_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

# 默认配置文件查找路径（相对于项目根）
_DEFAULT_CONFIG_PATHS = (
    Path("config/feishu.yaml"),
    Path(__file__).resolve().parent.parent.parent / "config" / "feishu.yaml",
)


class RateLimitConfig(BaseModel):
    """限流配置（FR-6）。"""

    msg_qps: int = 5
    base_batch_size: int = 200
    base_batch_interval_sec: float = 0.5


class RetryConfig(BaseModel):
    """重试配置（指数退避）。"""

    max_attempts: int = 3
    backoff_base: float = 1.0


class TableConfig(BaseModel):
    """单张表的配置项。"""

    name: str
    table_id: str = ""
    fields_file: str


class FeishuConfig(BaseModel):
    """飞书 IO 层总配置（对应 config/feishu.yaml）。"""

    app_id: str = ""
    app_secret: str = ""
    user_open_id: str = ""
    base_token: str = ""
    base_url: str = ""
    tables: list[TableConfig] = Field(default_factory=list)
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    def table_by_name(self, name: str) -> TableConfig | None:
        """按中文名查表配置。"""
        for t in self.tables:
            if t.name == name:
                return t
        return None


def _expand_env(value: Any) -> Any:
    """递归展开字符串中的 ${VAR} 环境变量占位符。"""
    if isinstance(value, str):
        def _repl(m: re.Match) -> str:
            return os.environ.get(m.group(1), m.group(0))

        return _ENV_PATTERN.sub(_repl, value)
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    return value


def validate_credentials(config: FeishuConfig) -> None:
    """校验必要凭证；缺失抛 FeishuNotConfigured。"""
    missing: list[str] = []
    if not config.app_id:
        missing.append("app_id (FEISHU_APP_ID)")
    if not config.app_secret:
        missing.append("app_secret (FEISHU_APP_SECRET)")
    if missing:
        raise FeishuNotConfigured(
            "缺少飞书凭证：" + "、".join(missing)
            + "。请设置环境变量后重试，或运行 `lark-cli config init` 完成 appId/appSecret 配置。"
        )


def load_feishu_config(
    path: str | Path | None = None,
    *,
    strict: bool = True,
) -> FeishuConfig:
    """加载飞书配置。

    Args:
        path: 指定 yaml 路径；None 时按 _DEFAULT_CONFIG_PATHS 依次查找。
        strict: True 时缺凭证抛 FeishuNotConfigured；False 时仅警告（供 health 等诊断用）。

    Returns:
        FeishuConfig 实例（环境变量已展开）。
    """
    candidates = [Path(path)] if path else list(_DEFAULT_CONFIG_PATHS)
    raw: dict[str, Any] = {}
    for candidate in candidates:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            logger.debug("加载飞书配置：{}", candidate)
            break
    else:
        logger.warning("未找到 feishu.yaml，使用默认配置（候选路径: {}）", candidates)

    raw = _expand_env(raw)
    config = FeishuConfig(**raw)
    if strict:
        validate_credentials(config)
    return config


def dump_feishu_config(config: FeishuConfig, path: str | Path) -> None:
    """将配置写回 yaml（init_base 写回 base_token / table_id 后使用）。

    注意：app_id/app_secret 写回的是展开后的明文；调用方应确保只写回本地文件。
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = config.model_dump()
    with open(p, "w", encoding="utf-8") as f:
        yaml.safe_dump(payload, f, allow_unicode=True, sort_keys=False)
