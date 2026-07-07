"""数据层配置加载与日志初始化。

按 plan §1.3 从 config/data.yaml 加载，用 Pydantic 做类型校验。
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from loguru import logger
from pydantic import BaseModel, Field


class RateLimitConfig(BaseModel):
    """限流配置。"""

    min_interval_seconds: float = 1.0
    max_concurrency: int = 1


class RetryConfig(BaseModel):
    """重试配置（指数退避）。"""

    max_attempts: int = 3
    backoff_base: float = 1.0


class LoggingConfig(BaseModel):
    """日志配置。"""

    level: str = "INFO"
    log_dir: str = "logs"
    rotation_bytes: int = 10 * 1024 * 1024
    retention_days: int = 30


class DataConfig(BaseModel):
    """数据层总配置（对应 config/data.yaml）。

    通过 `load_data_config()` 加载，下游模块注入使用。
    """

    cache_dir: str = "data/cache"
    rate_limit: RateLimitConfig = Field(default_factory=RateLimitConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    user_agents: list[str] = Field(default_factory=list)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

    @property
    def cache_path(self) -> Path:
        return Path(self.cache_dir)

    @property
    def nav_dir(self) -> Path:
        return self.cache_path / "nav"

    @property
    def holdings_dir(self) -> Path:
        return self.cache_path / "holdings"

    @property
    def meta_db_path(self) -> Path:
        return self.cache_path / "meta.db"

    def ensure_dirs(self) -> None:
        """创建缓存所需的全部目录。"""
        for d in (self.cache_path, self.nav_dir, self.holdings_dir):
            d.mkdir(parents=True, exist_ok=True)


# 默认配置文件查找路径（相对于项目根）
_DEFAULT_CONFIG_PATHS = (
    Path("config/data.yaml"),
    Path(__file__).resolve().parent.parent.parent / "config" / "data.yaml",
)


def load_data_config(path: str | Path | None = None) -> DataConfig:
    """加载数据层配置。

    Args:
        path: 指定 yaml 路径；None 时按 _DEFAULT_CONFIG_PATHS 依次查找，找不到用默认值。

    Returns:
        DataConfig 实例。
    """
    candidates = [Path(path)] if path else list(_DEFAULT_CONFIG_PATHS)
    for candidate in candidates:
        if candidate.is_file():
            with open(candidate, encoding="utf-8") as f:
                raw = yaml.safe_load(f) or {}
            return DataConfig(**raw)
    # 没找到配置文件，用 Pydantic 默认值
    logger.warning("未找到 data.yaml，使用默认配置（候选路径: {}）", candidates)
    return DataConfig()


def setup_logging(config: DataConfig) -> None:
    """配置 loguru：控制台 + 本地文件轮转。

    日志文件位于 `{config.logging.log_dir}/data-{{date}}.log`，按大小轮转。
    幂等：重复调用会先 remove 已有 handler。
    """
    log_cfg = config.logging
    log_dir = Path(log_cfg.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.remove()
    # 控制台：彩色精简
    logger.add(
        sys.stderr,
        level=log_cfg.level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | <cyan>{name}</cyan>:{line} - <level>{message}</level>",
    )
    # 文件：完整带日期，按大小轮转
    logger.add(
        log_dir / "data-{time:YYYY-MM-DD}.log",
        level=log_cfg.level,
        rotation=log_cfg.rotation_bytes,
        retention=f"{log_cfg.retention_days} days",
        encoding="utf-8",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <7} | {name}:{function}:{line} - {message}",
    )
