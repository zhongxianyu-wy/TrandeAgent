"""数据新鲜度报告（plan §3.2 / FR-7）。

每次拉取后写入 data_freshness 表；提供查询与统计接口。
"""
from __future__ import annotations

from datetime import date
from typing import Literal

import pandas as pd
from loguru import logger

from src.data.cache import MetaDB

# 新鲜度来源标记
FreshnessSource = Literal["cache", "fresh", "failed"]


class FreshnessReport:
    """新鲜度报告管理器（封装 MetaDB 的 data_freshness 表操作）。"""

    def __init__(self, meta_db: MetaDB) -> None:
        self._db = meta_db

    def record(
        self,
        fund_code: str,
        field_name: str,
        last_update: str | date | None,
        is_stale: bool,
        source: FreshnessSource,
        fail_reason: str | None = None,
    ) -> None:
        """记录单条新鲜度。"""
        self._db.upsert_freshness(
            fund_code=fund_code,
            field_name=field_name,
            last_update=last_update,
            is_stale=is_stale,
            source=source,
            fail_reason=fail_reason,
        )

    def record_fresh(
        self, fund_code: str, field_name: str, last_update: str | date
    ) -> None:
        """快捷方法：标记为新鲜拉取成功。"""
        self.record(fund_code, field_name, last_update, is_stale=False, source="fresh")

    def record_cache_hit(
        self, fund_code: str, field_name: str, last_update: str | date
    ) -> None:
        """快捷方法：标记为缓存命中。"""
        self.record(fund_code, field_name, last_update, is_stale=False, source="cache")

    def record_failure(
        self,
        fund_code: str,
        field_name: str,
        fail_reason: str,
        last_update: str | date | None = None,
    ) -> None:
        """快捷方法：标记为拉取失败，降级到缓存。

        若 last_update 为 None 表示无任何历史缓存。
        """
        self.record(
            fund_code,
            field_name,
            last_update,
            is_stale=True,
            source="failed",
            fail_reason=fail_reason,
        )

    def get_report(
        self,
        fund_code: str | None = None,
        is_stale: bool | None = None,
    ) -> pd.DataFrame:
        """查询新鲜度明细。"""
        return self._db.get_freshness(fund_code=fund_code, is_stale=is_stale)

    def summary(self) -> dict:
        """统计概览，用于 CLI `status` 命令。

        Returns:
            dict: total_records, stale_count, failed_count, by_source, by_field
        """
        df = self._db.get_freshness()
        if df.empty:
            return {"total_records": 0}
        result: dict = {
            "total_records": int(len(df)),
            "stale_count": int(df["is_stale"].sum()),
            "by_source": df["source"].value_counts().to_dict(),
            "by_field": df["field_name"].value_counts().to_dict(),
        }
        result["failed_count"] = int(
            df.get("source", pd.Series(dtype=str)).eq("failed").sum()
        )
        return result

    def log_summary(self) -> None:
        """打印新鲜度统计到日志。"""
        s = self.summary()
        if s.get("total_records", 0) == 0:
            logger.info("新鲜度报告：暂无记录")
            return
        logger.info(
            "新鲜度报告：共 {total} 条 | 过期 {stale} | 失败 {failed} | 来源分布 {sources}",
            total=s["total_records"],
            stale=s["stale_count"],
            failed=s["failed_count"],
            sources=s["by_source"],
        )
