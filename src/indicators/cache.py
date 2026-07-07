"""指标缓存层（T13）。

SQLite 存储，表结构对应 plan §2 的 indicator_cache。
缓存粒度：(fund_code, as_of_date, layer)。整组指标存 layer="full"。
同日重复计算直接走缓存（AC-4）。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date
from pathlib import Path

from loguru import logger

from src.indicators.models import FundIndicators

_INDICATOR_CACHE_DDL = """
CREATE TABLE IF NOT EXISTS indicator_cache (
    fund_code     TEXT NOT NULL,
    as_of_date    TEXT NOT NULL,
    layer         TEXT NOT NULL,
    indicators    TEXT,
    updated_at    TEXT DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (fund_code, as_of_date, layer)
);
"""

_LAYER_FULL = "full"


class IndicatorCache:
    """指标结果缓存（SQLite）。

    线程安全：单连接 + Lock（与 src.data.cache.MetaDB 风格一致）。
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute(_INDICATOR_CACHE_DDL)

    def get(self, fund_code: str, as_of_date: date) -> FundIndicators | None:
        """读取整组指标缓存；未命中返回 None。"""
        key = as_of_date.isoformat()
        with self._lock:
            row = self._conn.execute(
                "SELECT indicators FROM indicator_cache "
                "WHERE fund_code = ? AND as_of_date = ? AND layer = ?",
                (fund_code, key, _LAYER_FULL),
            ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row["indicators"])
            return FundIndicators.model_validate(data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning("指标缓存反序列化失败 {} {}: {}", fund_code, key, e)
            return None

    def set(self, indicators: FundIndicators) -> None:
        """写入整组指标缓存。"""
        fund_code = indicators.fund_code
        key = indicators.as_of_date.isoformat()
        payload = json.dumps(
            indicators.model_dump(mode="json"), ensure_ascii=False
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO indicator_cache "
                "(fund_code, as_of_date, layer, indicators) "
                "VALUES (?, ?, ?, ?) "
                "ON CONFLICT(fund_code, as_of_date, layer) DO UPDATE SET "
                "indicators=excluded.indicators, "
                "updated_at=datetime('now', 'localtime')",
                (fund_code, key, _LAYER_FULL, payload),
            )

    def invalidate(self, fund_code: str | None = None) -> int:
        """失效缓存。fund_code=None 清空全部；返回删除行数。"""
        with self._lock:
            if fund_code is None:
                cur = self._conn.execute("DELETE FROM indicator_cache")
            else:
                cur = self._conn.execute(
                    "DELETE FROM indicator_cache WHERE fund_code = ?",
                    (fund_code,),
                )
            return cur.rowcount

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "IndicatorCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
