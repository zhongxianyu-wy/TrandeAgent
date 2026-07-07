"""飞书 IO 层错误码与异常定义（plan §3 / FR-6 / FR-8 / Step6 §2.6）。

错误码处理协议：
- 1254104：批量写入超限 → 调用方自动降批到 100 重试
- 91403：无权限访问资源 → 记录告警日志，不中断主流程
- 1254064：日期格式错误 → 抛 SchemaError，不重试
- exit code 10：高风险操作门禁拦截 → 抛 SecurityError，禁止自动加 --yes 绕过
"""
from __future__ import annotations


class FeishuError(Exception):
    """飞书 IO 层基础异常。"""


class LarkCLINotInstalled(FeishuError):
    """lark-cli 二进制未安装或不在 PATH。"""


class FeishuNotConfigured(FeishuError):
    """缺少 appId/appSecret 等必要配置。"""


class SecurityError(FeishuError):
    """高风险操作门禁拦截（lark-cli exit code 10）。

    绝对禁止自动追加 --yes 绕过门禁（违反 SKILL.md 原文）。
    正确做法：抛出本异常 → 上层向用户确认 → 用户显式同意后再加 --yes 重试。
    """


class SchemaError(FeishuError):
    """数据/卡片 schema 校验失败（如 1254064 日期格式错）。不可重试。"""


class BatchLimitExceeded(FeishuError):
    """批量写入超限（1254104）。调用方应降批后重试。"""


class PermissionDenied(FeishuError):
    """无权限访问目标资源（91403）。默认告警不中断。"""


class LarkCLITransientError(FeishuError):
    """lark-cli 调用瞬时失败（网络抖动等），可重试。"""


# 飞书 API 错误码 → 异常类型映射
ERROR_CODE_MAP: dict[int, type[FeishuError]] = {
    1254104: BatchLimitExceeded,  # 批量写入超限
    91403: PermissionDenied,       # 无权限
    1254064: SchemaError,          # 日期格式错误
}

# 批量超限时自动降批的目标大小（plan FR-6 / FR-3）
DEGRADED_BATCH_SIZE = 100


def classify_api_error(code: int, message: str = "") -> FeishuError:
    """根据飞书 API 错误码构造对应异常。

    已知码返回业务异常；未知码归为可重试的 LarkCLITransientError。
    """
    exc_cls = ERROR_CODE_MAP.get(code, LarkCLITransientError)
    text = f"[{code}] {message}" if message else f"[{code}]"
    return exc_cls(text)
