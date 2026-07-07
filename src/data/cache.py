"""本地缓存层：SQLite（元数据）+ Parquet（时序净值/持仓）。

设计依据 plan §2.1 / §2.2：
- 元数据（基金基本信息、经理、新鲜度）用 SQLite，关系查询灵活
- 时序数据（日频净值、季度持仓）用 Parquet，列式压缩，回测批量读极快

所有写入线程安全（SQLite 用专用连接 + Lock；Parquet 单写入线程）。
"""
from __future__ import annotations

import sqlite3
import threading
from datetime import date
from pathlib import Path

import pandas as pd
from loguru import logger

# SQLite 表 DDL（plan §2.1）
_FUND_BASIC_DDL = """
CREATE TABLE IF NOT EXISTS fund_basic (
    fund_code        TEXT PRIMARY KEY,
    fund_name        TEXT NOT NULL,
    fund_type        TEXT NOT NULL,
    fund_category    TEXT NOT NULL,
    pinyin_abbr      TEXT,
    manager_names    TEXT,
    management_co    TEXT,
    custodian_co     TEXT,
    establish_date   TEXT,
    latest_scale     REAL,
    management_fee   REAL,
    custodian_fee    REAL,
    history_months   INTEGER,
    updated_at       TEXT DEFAULT (datetime('now', 'localtime'))
);
"""

_FUND_BASIC_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_fund_basic_category ON fund_basic(fund_category);"
)

_FUND_MANAGER_DDL = """
CREATE TABLE IF NOT EXISTS fund_manager (
    manager_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    manager_name     TEXT NOT NULL,
    fund_code        TEXT NOT NULL,
    start_date       TEXT,
    end_date         TEXT,
    tenure_years     REAL,
    total_assets     REAL,
    FOREIGN KEY (fund_code) REFERENCES fund_basic(fund_code)
);
"""

_FUND_MANAGER_INDEX_DDL = (
    "CREATE INDEX IF NOT EXISTS idx_fund_manager_code ON fund_manager(fund_code);"
)

_DATA_FRESHNESS_DDL = """
CREATE TABLE IF NOT EXISTS data_freshness (
    fund_code        TEXT NOT NULL,
    field_name       TEXT NOT NULL,
    last_update      TEXT,
    is_stale         INTEGER DEFAULT 0,
    source           TEXT,
    fail_reason      TEXT,
    updated_at       TEXT DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (fund_code, field_name)
);
"""


class MetaDB:
    """SQLite 元数据缓存（fund_basic / fund_manager / data_freshness）。

    WAL 模式以支持读写并发；单连接 + Lock 保证写入线程安全。
    """

    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(
            str(self._path),
            check_same_thread=False,
            isolation_level=None,  # autocommit，配合显式事务
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        # 外键关闭：AkShare 数据可能乱序到达（经理先于 fund_basic），不强制约束
        self._conn.execute("PRAGMA foreign_keys=OFF;")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.executescript(
                _FUND_BASIC_DDL
                + _FUND_BASIC_INDEX_DDL
                + _FUND_MANAGER_DDL
                + _FUND_MANAGER_INDEX_DDL
                + _DATA_FRESHNESS_DDL
            )

    # ----- fund_basic -----
    def upsert_fund_basic(self, row: dict) -> None:
        """upsert 单条基金基本信息。"""
        cols = (
            "fund_code, fund_name, fund_type, fund_category, pinyin_abbr, "
            "manager_names, management_co, custodian_co, establish_date, "
            "latest_scale, management_fee, custodian_fee, history_months"
        )
        placeholders = ", ".join(["?"] * 13)
        sql = (
            f"INSERT INTO fund_basic ({cols}) VALUES ({placeholders}) "
            "ON CONFLICT(fund_code) DO UPDATE SET "
            "fund_name=excluded.fund_name, fund_type=excluded.fund_type, "
            "fund_category=excluded.fund_category, pinyin_abbr=excluded.pinyin_abbr, "
            "manager_names=excluded.manager_names, management_co=excluded.management_co, "
            "custodian_co=excluded.custodian_co, establish_date=excluded.establish_date, "
            "latest_scale=excluded.latest_scale, management_fee=excluded.management_fee, "
            "custodian_fee=excluded.custodian_fee, history_months=excluded.history_months, "
            "updated_at=datetime('now', 'localtime')"
        )
        with self._lock:
            self._conn.execute(
                sql,
                (
                    row.get("fund_code"),
                    row.get("fund_name"),
                    row.get("fund_type"),
                    row.get("fund_category"),
                    row.get("pinyin_abbr"),
                    row.get("manager_names"),
                    row.get("management_co"),
                    row.get("custodian_co"),
                    row.get("establish_date"),
                    row.get("latest_scale"),
                    row.get("management_fee"),
                    row.get("custodian_fee"),
                    row.get("history_months"),
                ),
            )

    def upsert_fund_basic_batch(self, rows: list[dict]) -> int:
        """批量 upsert，返回写入条数。"""
        for row in rows:
            self.upsert_fund_basic(row)
        return len(rows)

    def get_fund_basic(
        self,
        fund_code: str | None = None,
        categories: list[str] | None = None,
    ) -> pd.DataFrame:
        """查询基金基本信息。

        Args:
            fund_code: 指定代码；None 表示全部。
            categories: 大类过滤（fund_category IN (...)）；None 表示不过滤。
        """
        sql = "SELECT * FROM fund_basic WHERE 1=1"
        params: list = []
        if fund_code is not None:
            sql += " AND fund_code = ?"
            params.append(fund_code)
        if categories:
            placeholders = ", ".join(["?"] * len(categories))
            sql += f" AND fund_category IN ({placeholders})"
            params.extend(categories)
        with self._lock:
            df = pd.read_sql_query(sql, self._conn, params=params)
        return df

    # ----- fund_manager -----
    def upsert_managers(self, fund_code: str, rows: list[dict]) -> int:
        """替换某基金的全部经理记录（先删后插）。"""
        with self._lock:
            self._conn.execute(
                "DELETE FROM fund_manager WHERE fund_code = ?", (fund_code,)
            )
            for row in rows:
                self._conn.execute(
                    "INSERT INTO fund_manager "
                    "(manager_name, fund_code, start_date, end_date, tenure_years, total_assets) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        row.get("manager_name"),
                        fund_code,
                        row.get("start_date"),
                        row.get("end_date"),
                        row.get("tenure_years"),
                        row.get("total_assets"),
                    ),
                )
        return len(rows)

    def get_managers(self, fund_code: str) -> pd.DataFrame:
        sql = "SELECT * FROM fund_manager WHERE fund_code = ? ORDER BY start_date"
        with self._lock:
            return pd.read_sql_query(sql, self._conn, params=(fund_code,))

    # ----- data_freshness -----
    def upsert_freshness(
        self,
        fund_code: str,
        field_name: str,
        last_update: str | date | None,
        is_stale: bool,
        source: str,
        fail_reason: str | None = None,
    ) -> None:
        sql = (
            "INSERT INTO data_freshness "
            "(fund_code, field_name, last_update, is_stale, source, fail_reason) "
            "VALUES (?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(fund_code, field_name) DO UPDATE SET "
            "last_update=excluded.last_update, is_stale=excluded.is_stale, "
            "source=excluded.source, fail_reason=excluded.fail_reason, "
            "updated_at=datetime('now', 'localtime')"
        )
        lu = last_update.isoformat() if isinstance(last_update, date) else last_update
        with self._lock:
            self._conn.execute(
                sql,
                (fund_code, field_name, lu, int(bool(is_stale)), source, fail_reason),
            )

    def get_freshness(
        self,
        fund_code: str | None = None,
        field_name: str | None = None,
        is_stale: bool | None = None,
    ) -> pd.DataFrame:
        sql = "SELECT * FROM data_freshness WHERE 1=1"
        params: list = []
        if fund_code is not None:
            sql += " AND fund_code = ?"
            params.append(fund_code)
        if field_name is not None:
            sql += " AND field_name = ?"
            params.append(field_name)
        if is_stale is not None:
            sql += " AND is_stale = ?"
            params.append(int(bool(is_stale)))
        with self._lock:
            return pd.read_sql_query(sql, self._conn, params=params)

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "MetaDB":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


class ParquetStore:
    """Parquet 时序缓存（nav / holdings）。

    文件组织：`{root}/{kind}/{fund_code}.parquet`。
    写入按主键去重（trade_date / report_date + stock_code）后覆盖。
    """

    def __init__(self, root: str | Path) -> None:
        self._root = Path(root)

    def _path(self, kind: str, fund_code: str) -> Path:
        d = self._root / kind
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{fund_code}.parquet"

    # ----- nav -----
    def write_nav(self, fund_code: str, df: pd.DataFrame) -> int:
        """追加净值并按 trade_date 去重，返回最终行数。"""
        if df.empty:
            return 0
        target = self._path("nav", fund_code)
        if target.exists():
            old = pd.read_parquet(target)
            combined = pd.concat([old, df], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=["trade_date"], keep="last"
            ).sort_values("trade_date")
        else:
            combined = df.sort_values("trade_date")
        combined.to_parquet(target, index=False)
        return len(combined)

    def read_nav(
        self, fund_code: str, start: date | None = None, end: date | None = None
    ) -> pd.DataFrame:
        """读取净值；按 [start, end] 过滤；无文件返回空 DataFrame。"""
        target = self._path("nav", fund_code)
        if not target.exists():
            return pd.DataFrame(
                columns=["trade_date", "unit_nav", "accum_nav", "daily_return", "is_adjusted"]
            )
        df = pd.read_parquet(target)
        if not df.empty:
            # 统一日期类型用于比较
            dt = pd.to_datetime(df["trade_date"]).dt.date
            mask = pd.Series(True, index=df.index)
            if start is not None:
                mask &= dt >= start
            if end is not None:
                mask &= dt <= end
            df = df[mask]
        return df.reset_index(drop=True)

    def nav_last_date(self, fund_code: str) -> date | None:
        """返回该基金已缓存净值的最后交易日；无则 None（用于增量判断）。"""
        target = self._path("nav", fund_code)
        if not target.exists():
            return None
        df = pd.read_parquet(target, columns=["trade_date"])
        if df.empty:
            return None
        last = pd.to_datetime(df["trade_date"]).max().date()
        return last

    # ----- holdings -----
    def write_holdings(self, fund_code: str, df: pd.DataFrame) -> int:
        if df.empty:
            return 0
        target = self._path("holdings", fund_code)
        if target.exists():
            old = pd.read_parquet(target)
            combined = pd.concat([old, df], ignore_index=True)
            combined = combined.drop_duplicates(
                subset=["report_date", "stock_code"], keep="last"
            ).sort_values(["report_date", "holding_pct"], ascending=[True, False])
        else:
            combined = df.sort_values(
                ["report_date", "holding_pct"], ascending=[True, False]
            )
        combined.to_parquet(target, index=False)
        return len(combined)

    def read_holdings(
        self, fund_code: str, report_date: date | None = None
    ) -> pd.DataFrame:
        target = self._path("holdings", fund_code)
        if not target.exists():
            return pd.DataFrame(
                columns=["report_date", "stock_code", "stock_name", "holding_pct", "industry"]
            )
        df = pd.read_parquet(target)
        if report_date is not None and not df.empty:
            dt = pd.to_datetime(df["report_date"]).dt.date
            df = df[dt == report_date]
        return df.reset_index(drop=True)

    def has_any_nav(self) -> bool:
        """nav 目录是否已有任何 .parquet 文件（用于首次启动检测）。"""
        nav_dir = self._root / "nav"
        if not nav_dir.exists():
            return False
        return any(nav_dir.glob("*.parquet"))
