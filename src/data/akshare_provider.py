"""AkShareProvider 实现（Feature #1 核心）。

封装 AkShare 上游调用 + 本地缓存 + 限流/重试/降级。
下游只依赖 `DataProvider` 接口，不直接 import 本类（DI 由 main 编排）。

字段映射依据真实接口探查（2026-07）：
- fund_name_em: 基金代码/拼音缩写/基金简称/基金类型/拼音全称
- fund_open_fund_info_em(单位净值走势): 净值日期/单位净值/日增长率
- fund_open_fund_info_em(累计净值走势): 净值日期/累计净值
- fund_portfolio_hold_em: 股票代码/股票名称/占净值比例/季度
- fund_manager_em: 姓名/所属公司/现任基金代码/累计从业时间/现任基金资产总规模
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Callable

import akshare as ak
import pandas as pd
from loguru import logger

from src.data.cache import MetaDB, ParquetStore
from src.data.config import DataConfig
from src.data.freshness import FreshnessReport
from src.data.provider import DataProvider, FundCategory
from src.data.rate_limit import RateLimiter, UARotator
from src.data.retry import UpstreamUnavailable, with_retry

# Clarify Q6：首次启动空缓存时，前台立即返回的 5 只样例基金 30 天数据
SAMPLE_FUND_CODES = ["000001", "161725", "005827", "004243", "161903"]

# 基金类型 → 大类的映射规则（T11）
# 显式排除：债基/货基/FOF/REITs/商品/固收
_EXCLUDE_KEYWORDS = ("债券", "货币", "FOF", "Reits", "REIT", "商品", "固收", "纯债")


def classify_category(fund_type: str, fund_name: str) -> FundCategory | None:
    """把 AkShare 的基金类型字符串映射到 4 大类；不属于目标范围的返回 None（剔除）。

    规则依据真实类型分布（fund_name_em）：
      - QDII（股票类）→ qdii
      - 指数型（股票/其他，非海外非固收）→ index
      - ETF 联接（名称含"ETF联接"）→ etf_link
      - 混合/股票型（偏股/灵活/平衡/绝对收益/股票型）→ active_stock
      - 债/货/FOF/REITs/商品/固收/海外指数（归 qdii 的除外）→ None
    """
    ft = (fund_type or "").strip()
    fn = (fund_name or "").strip()

    # 1. 名称含 ETF 联接优先识别
    if "ETF联接" in fn or "ETF 联接" in fn:
        return "etf_link"

    # 2. 排除明显非权益类
    for kw in _EXCLUDE_KEYWORDS:
        if kw in ft:
            return None

    # 3. QDII 股票类
    if "QDII" in ft:
        # QDII 混合偏股/普通股票/混合灵活/混合平衡 → qdii
        return "qdii"

    # 4. 海外指数归 qdii
    if "海外" in ft:
        return "qdii"

    # 5. 指数型（非海外非固收，到这里固收已排除）
    if ft.startswith("指数型"):
        return "index"

    # 6. 主动权益类
    if "混合型" in ft or ft == "股票型":
        return "active_stock"

    return None


def _parse_report_date(quarter_str: str) -> date | None:
    """从 '2024年1季度股票投资明细' 解析出季末日期。"""
    import re

    m = re.match(r"(\d{4})年(\d)季度", quarter_str or "")
    if not m:
        return None
    year, q = int(m.group(1)), int(m.group(2))
    month_end = {1: (3, 31), 2: (6, 30), 3: (9, 30), 4: (12, 31)}[q]
    return date(year, *month_end)


class AkShareProvider(DataProvider):
    """AkShare 数据源实现。"""

    def __init__(self, config: DataConfig | None = None) -> None:
        self._config = config or DataConfig()
        self._config.ensure_dirs()
        self._rate_limiter = RateLimiter(
            self._config.rate_limit.min_interval_seconds
        )
        ua_pool = self._config.user_agents or _DEFAULT_USER_AGENTS
        self._ua_rotator = UARotator(ua_pool)
        self._meta = MetaDB(self._config.meta_db_path)
        self._pq = ParquetStore(self._config.cache_path)
        self._freshness = FreshnessReport(self._meta)

    # ------------------------------------------------------------------
    # 上游调用封装（限流 + 重试 + UA）
    # ------------------------------------------------------------------
    def _call_upstream(self, func: Callable, *args, **kwargs):
        """带限流+重试的上游调用。失败抛 UpstreamUnavailable。"""
        self._rate_limiter.wait()
        return with_retry(
            func,
            *args,
            max_attempts=self._config.retry.max_attempts,
            backoff_base=self._config.retry.backoff_base,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # FR-1 / T09：list_funds
    # ------------------------------------------------------------------
    def list_funds(self, categories: list[FundCategory] | None = None) -> pd.DataFrame:
        """返回全市场基金基本信息（4 大类）。

        缓存命中（当日已刷新）直接返回；否则走上游 + 写缓存。
        """
        # 缓存判断：当日已更新则用缓存
        cached = self._meta.get_fund_basic(categories=categories)
        if not cached.empty and self._cache_is_fresh_today("fund_basic"):
            return cached

        try:
            raw = self._call_upstream(ak.fund_name_em)
            rows = self._parse_fund_list(raw)
            self._meta.upsert_fund_basic_batch(rows)
            self._freshness.record_fresh(
                "ALL", "fund_basic", date.today().isoformat()
            )
        except UpstreamUnavailable as e:
            logger.warning("list_funds 上游失败，降级到缓存：{}", e)
            self._freshness.record_failure("ALL", "fund_basic", str(e))
            if cached.empty:
                raise
            return self._filter_by_categories(cached, categories)

        df = self._meta.get_fund_basic(categories=categories)
        return df

    @staticmethod
    def _parse_fund_list(raw: pd.DataFrame) -> list[dict]:
        """把 fund_name_em 原始返回映射成 fund_basic 行。"""
        rows: list[dict] = []
        for _, r in raw.iterrows():
            fund_type = str(r.get("基金类型", ""))
            fund_name = str(r.get("基金简称", ""))
            category = classify_category(fund_type, fund_name)
            if category is None:
                continue
            rows.append(
                {
                    "fund_code": str(r.get("基金代码", "")).zfill(6),
                    "fund_name": fund_name,
                    "fund_type": fund_type,
                    "fund_category": category,
                    "pinyin_abbr": str(r.get("拼音缩写", "")),
                    "manager_names": None,  # fund_name_em 不含经理，由 get_manager 补
                    "management_co": None,
                    "custodian_co": None,
                    "establish_date": None,
                    "latest_scale": None,
                    "management_fee": None,
                    "custodian_fee": None,
                    "history_months": None,
                }
            )
        return rows

    @staticmethod
    def _filter_by_categories(
        df: pd.DataFrame, categories: list[FundCategory] | None
    ) -> pd.DataFrame:
        if categories is None or df.empty:
            return df
        return df[df["fund_category"].isin(categories)].reset_index(drop=True)

    def _cache_is_fresh_today(self, field_name: str) -> bool:
        """检查 data_freshness 表中某字段是否今日已更新。"""
        rep = self._meta.get_freshness(fund_code="ALL", field_name=field_name)
        if rep.empty:
            return False
        last = rep.iloc[0]["last_update"]
        return str(last) == date.today().isoformat()

    # ------------------------------------------------------------------
    # FR-2 / T10：get_nav
    # ------------------------------------------------------------------
    def get_nav(self, fund_code: str, start: date, end: date) -> pd.DataFrame:
        """获取日频净值序列（缓存优先）。"""
        cached = self._pq.read_nav(fund_code, start, end)
        if not cached.empty:
            self._freshness.record_cache_hit(
                fund_code, "nav", self._pq.nav_last_date(fund_code).isoformat()
                if self._pq.nav_last_date(fund_code)
                else None
            )
            return cached

        # 缓存空 → 上游拉取全量并写缓存
        try:
            df = self._fetch_nav_raw(fund_code)
            self._pq.write_nav(fund_code, df)
            self._freshness.record_fresh(
                fund_code, "nav", date.today().isoformat()
            )
        except UpstreamUnavailable as e:
            logger.warning("get_nav {} 上游失败，降级到缓存：{}", fund_code, e)
            self._freshness.record_failure(fund_code, "nav", str(e))
            return cached

        return self._pq.read_nav(fund_code, start, end)

    def _fetch_nav_raw(self, fund_code: str) -> pd.DataFrame:
        """合并单位净值与累计净值。"""
        unit_df = self._call_upstream(
            ak.fund_open_fund_info_em,
            symbol=fund_code,
            indicator="单位净值走势",
        )
        if unit_df is None or unit_df.empty:
            return pd.DataFrame(
                columns=["trade_date", "unit_nav", "accum_nav", "daily_return", "is_adjusted"]
            )
        unit_df = unit_df.rename(
            columns={"净值日期": "trade_date", "单位净值": "unit_nav", "日增长率": "daily_return"}
        )
        unit_df["trade_date"] = pd.to_datetime(unit_df["trade_date"]).dt.date

        # 累计净值（失败则用单位净值降级）
        try:
            accum_df = self._call_upstream(
                ak.fund_open_fund_info_em,
                symbol=fund_code,
                indicator="累计净值走势",
            )
            accum_df = accum_df.rename(columns={"净值日期": "trade_date", "累计净值": "accum_nav"})
            accum_df["trade_date"] = pd.to_datetime(accum_df["trade_date"]).dt.date
            merged = unit_df.merge(accum_df[["trade_date", "accum_nav"]], on="trade_date", how="left")
            merged["accum_nav"] = merged["accum_nav"].fillna(merged["unit_nav"])
        except UpstreamUnavailable:
            merged = unit_df.copy()
            merged["accum_nav"] = merged["unit_nav"]

        merged["is_adjusted"] = True
        return merged[
            ["trade_date", "unit_nav", "accum_nav", "daily_return", "is_adjusted"]
        ]

    # ------------------------------------------------------------------
    # FR-3 / T10：get_holdings
    # ------------------------------------------------------------------
    def get_holdings(self, fund_code: str, report_date: date | None = None) -> pd.DataFrame:
        cached = self._pq.read_holdings(fund_code, report_date)
        if not cached.empty:
            self._freshness.record_cache_hit(fund_code, "holdings", None)
            return cached
        # 缓存空 → 拉取今年持仓
        try:
            years = [str(date.today().year)]
            if report_date is not None:
                years = [str(report_date.year)]
            frames = []
            for y in years:
                raw = self._call_upstream(
                    ak.fund_portfolio_hold_em, symbol=fund_code, date=y
                )
                frames.append(self._parse_holdings(raw))
            df = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            if not df.empty:
                self._pq.write_holdings(fund_code, df)
                self._freshness.record_fresh(fund_code, "holdings", date.today().isoformat())
            else:
                self._freshness.record_failure(fund_code, "holdings", "无持仓数据")
            return self._pq.read_holdings(fund_code, report_date)
        except UpstreamUnavailable as e:
            logger.warning("get_holdings {} 上游失败，降级到缓存：{}", fund_code, e)
            self._freshness.record_failure(fund_code, "holdings", str(e))
            return cached

    @staticmethod
    def _parse_holdings(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty:
            return pd.DataFrame(
                columns=["report_date", "stock_code", "stock_name", "holding_pct", "industry"]
            )
        df = pd.DataFrame(
            {
                "report_date": raw["季度"].apply(_parse_report_date),
                "stock_code": raw["股票代码"].astype(str),
                "stock_name": raw["股票名称"].astype(str),
                "holding_pct": pd.to_numeric(raw["占净值比例"], errors="coerce"),
                "industry": None,  # AkShare 此接口不返回行业，留空
            }
        )
        return df.dropna(subset=["report_date"]).reset_index(drop=True)

    # ------------------------------------------------------------------
    # FR-3 / T09：get_manager
    # ------------------------------------------------------------------
    def get_manager(self, fund_code: str) -> pd.DataFrame:
        cached = self._meta.get_managers(fund_code)
        if not cached.empty:
            return cached
        try:
            raw = self._call_upstream(ak.fund_manager_em)
            rows = self._parse_managers(raw, fund_code)
            self._meta.upsert_managers(fund_code, rows)
            self._freshness.record_fresh(
                fund_code, "manager", date.today().isoformat()
            )
        except UpstreamUnavailable as e:
            logger.warning("get_manager {} 上游失败，降级到缓存：{}", fund_code, e)
            self._freshness.record_failure(fund_code, "manager", str(e))
        return self._meta.get_managers(fund_code)

    @staticmethod
    def _parse_managers(raw: pd.DataFrame, fund_code: str) -> list[dict]:
        """从 fund_manager_em（经理维度）过滤出指定基金的现任经理。"""
        if raw is None or raw.empty:
            return []
        sub = raw[raw["现任基金代码"].astype(str).str.zfill(6) == fund_code]
        rows: list[dict] = []
        for _, r in sub.iterrows():
            days = pd.to_numeric(r.get("累计从业时间"), errors="coerce")
            tenure = float(days) / 365.0 if pd.notna(days) else None
            scale = pd.to_numeric(r.get("现任基金资产总规模"), errors="coerce")
            rows.append(
                {
                    "manager_name": str(r.get("姓名", "")),
                    "start_date": None,
                    "end_date": None,
                    "tenure_years": tenure,
                    "total_assets": float(scale) if pd.notna(scale) else None,
                }
            )
        return rows

    # ------------------------------------------------------------------
    # FR-7：新鲜度报告
    # ------------------------------------------------------------------
    def get_freshness_report(self) -> pd.DataFrame:
        return self._freshness.get_report()

    # ------------------------------------------------------------------
    # FR-2 增量 / FR-2 全量回填
    # ------------------------------------------------------------------
    def refresh_incremental(self, fund_codes: list[str] | None = None) -> dict:
        """增量更新：只拉取每只基金缺失的最近净值。"""
        codes = fund_codes or self._all_fund_codes()
        logger.info("增量更新 {} 只基金", len(codes))
        for code in codes:
            last = self._pq.nav_last_date(code)
            today = date.today()
            if last is not None and last >= today:
                self._freshness.record_cache_hit(code, "nav", last.isoformat())
                continue
            try:
                df = self._fetch_nav_raw(code)
                # 增量只写 last 之后的数据（若已有缓存）
                if last is not None:
                    df = df[pd.to_datetime(df["trade_date"]).dt.date > last]
                if not df.empty:
                    self._pq.write_nav(code, df)
                self._freshness.record_fresh(code, "nav", today.isoformat())
            except UpstreamUnavailable as e:
                self._freshness.record_failure(code, "nav", str(e))
        return self._freshness.summary()

    def refresh_full_backfill(self, fund_codes: list[str], years: int = 5) -> dict:
        """全量回填：拉取指定基金的全部历史净值。"""
        start = date.today() - timedelta(days=365 * years)
        logger.info("全量回填 {} 只基金，起始 {}", len(fund_codes), start)
        for code in fund_codes:
            try:
                df = self._fetch_nav_raw(code)
                if not df.empty:
                    self._pq.write_nav(code, df)
                self._freshness.record_fresh(code, "nav", date.today().isoformat())
            except UpstreamUnavailable as e:
                self._freshness.record_failure(code, "nav", str(e))
        return self._freshness.summary()

    def _all_fund_codes(self) -> list[str]:
        df = self._meta.get_fund_basic()
        if df.empty:
            try:
                self.list_funds()
                df = self._meta.get_fund_basic()
            except UpstreamUnavailable:
                return SAMPLE_FUND_CODES
        return df["fund_code"].astype(str).tolist()

    # ------------------------------------------------------------------
    # Clarify Q6：空缓存时返回样例
    # ------------------------------------------------------------------
    def get_sample_nav(self) -> dict[str, pd.DataFrame]:
        """空缓存启动时返回 5 只样例基金的近 30 天净值（尽力拉取，失败返空）。"""
        today = date.today()
        start = today - timedelta(days=30)
        result: dict[str, pd.DataFrame] = {}
        for code in SAMPLE_FUND_CODES:
            try:
                df = self._fetch_nav_raw(code)
                if not df.empty:
                    df = df[pd.to_datetime(df["trade_date"]).dt.date >= start]
                result[code] = df
            except UpstreamUnavailable:
                result[code] = pd.DataFrame()
        return result

    def close(self) -> None:
        self._meta.close()


# 默认 UA 池（当 config.user_agents 为空时用）
_DEFAULT_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:127.0) Gecko/20100101 Firefox/127.0",
]
