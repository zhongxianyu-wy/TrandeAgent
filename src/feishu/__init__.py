"""飞书 IO 层（Feature #2 feishu-io）。

封装飞书侧所有 IO（单聊卡片推送 + 多维表格读写），对下游业务模块提供
统一 `FeishuClient` 接口，隐藏 lark-cli subprocess 调用细节。
"""
from src.feishu.cards import BaseRecord, CardAction, CardElement, FeishuCard
from src.feishu.client import FeishuClient
from src.feishu.config import (
    FeishuConfig,
    load_feishu_config,
    validate_credentials,
)
from src.feishu.error_codes import (
    BatchLimitExceeded,
    FeishuError,
    FeishuNotConfigured,
    LarkCLINotInstalled,
    LarkCLITransientError,
    PermissionDenied,
    SchemaError,
    SecurityError,
)
from src.feishu.lark_cli_client import LarkCLIClient

__all__ = [
    "FeishuClient",
    "LarkCLIClient",
    "FeishuConfig",
    "load_feishu_config",
    "validate_credentials",
    "FeishuCard",
    "CardElement",
    "CardAction",
    "BaseRecord",
    "FeishuError",
    "FeishuNotConfigured",
    "LarkCLINotInstalled",
    "LarkCLITransientError",
    "PermissionDenied",
    "SchemaError",
    "SecurityError",
    "BatchLimitExceeded",
]
