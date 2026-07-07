"""配置加载（T14）。

对应 config/analyzer.yaml（含 LLM provider 选择）。文件缺失时使用内置默认值，
保证 analyzer 在无配置文件时仍可运行（凭证从环境变量取）。
${VAR} 形式的环境变量占位符自动展开。
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")

_DEFAULT_CONFIG_PATHS = (
    Path("config/analyzer.yaml"),
    Path(__file__).resolve().parent.parent.parent / "config" / "analyzer.yaml",
)

LLMProvider = Literal["deepseek", "qwen"]


class LLMConfig(BaseModel):
    """LLM 客户端配置。"""

    provider: LLMProvider = "deepseek"
    api_key: str = ""  # 运行时从环境变量填充
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-chat"
    timeout: float = 60.0


class AnalyzerConfig(BaseModel):
    """fund-analyzer 总配置。"""

    funds: list[str] = Field(default_factory=list)  # 配置文件触发的基金代码
    years: int = 5  # 回溯年数
    max_retries: int = 1  # 后校验失败重试次数（不含首次）
    llm: LLMConfig = Field(default_factory=LLMConfig)


def _expand_env(value: Any, environ: dict[str, str]) -> Any:
    """递归展开字符串中的 ${VAR} 占位符（用传入的 environ）。"""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(
            lambda m: environ.get(m.group(1), m.group(0)), value
        )
    if isinstance(value, list):
        return [_expand_env(v, environ) for v in value]
    if isinstance(value, dict):
        return {k: _expand_env(v, environ) for k, v in value.items()}
    return value


def _resolve_api_key(provider: LLMProvider, explicit: str, environ: dict[str, str]) -> str:
    """api_key 解析：显式值优先，否则按 provider 取环境变量。"""
    if explicit:
        return explicit
    env_map = {
        "deepseek": ("DEEPSEEK_API_KEY", "OPENAI_API_KEY"),
        "qwen": ("DASHSCOPE_API_KEY", "QWEN_API_KEY"),
    }
    for env_name in env_map.get(provider, ()):
        val = environ.get(env_name, "")
        if val:
            return val
    return ""


def load_analyzer_config(
    path: str | Path | None = None,
    *,
    env: dict[str, str] | None = None,
) -> AnalyzerConfig:
    """加载 analyzer 配置。

    Args:
        path: 指定 yaml 路径；None 时按默认候选路径查找，缺失则用默认值。
        env: 测试用注入环境变量（默认读 os.environ）。

    Returns:
        AnalyzerConfig（环境变量已展开，api_key 已按 provider 解析）。
    """
    environ = env if env is not None else os.environ
    raw: dict[str, Any] = {}
    candidates = [Path(path)] if path else list(_DEFAULT_CONFIG_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            break

    raw = _expand_env(raw, environ)
    config = AnalyzerConfig(**raw)
    config.llm.api_key = _resolve_api_key(config.llm.provider, config.llm.api_key, environ)
    return config


def build_llm_client(config: AnalyzerConfig, *, llm_config: LLMConfig | None = None):
    """按配置构造 LLMClient 实例。

    Args:
        config: analyzer 总配置。
        llm_config: 可选覆盖（CLI --provider 切换时使用）。

    Returns:
        LLMClient 实例。无 api_key 时抛 ValueError。
    """
    from src.analyzer.llm import DeepSeekClient, QwenClient

    cfg = llm_config or config.llm
    if cfg.provider == "qwen":
        return QwenClient(api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model, timeout=cfg.timeout)
    return DeepSeekClient(api_key=cfg.api_key, base_url=cfg.base_url, model=cfg.model, timeout=cfg.timeout)
