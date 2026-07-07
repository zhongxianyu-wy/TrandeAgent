"""pytest 全局 fixtures（Feature #1 data-provider）。"""
from __future__ import annotations

import pandas as pd
import pytest

from src.data.config import DataConfig
from src.data.cache import MetaDB, ParquetStore


@pytest.fixture
def tmp_config(tmp_path) -> DataConfig:
    """临时 DataConfig，所有缓存指向 tmp_path。"""
    return DataConfig(cache_dir=str(tmp_path / "cache"))


@pytest.fixture
def meta_db(tmp_config) -> MetaDB:
    db = MetaDB(tmp_config.meta_db_path)
    yield db
    db.close()


@pytest.fixture
def parquet_store(tmp_config) -> ParquetStore:
    return ParquetStore(tmp_config.cache_path)


# ---- AkShare mock fixtures（字段对齐真实接口探查结果） ----


@pytest.fixture
def mock_fund_name_df() -> pd.DataFrame:
    """模拟 ak.fund_name_em() 返回，覆盖 4 大类 + 被剔除类型。"""
    return pd.DataFrame(
        [
            {"基金代码": "000001", "拼音缩写": "HXCZHH", "基金简称": "华夏成长混合", "基金类型": "混合型-偏股", "拼音全称": "HUAXIA"},
            {"基金代码": "161725", "拼音缩写": "ZSBJ", "基金简称": "招商中证白酒指数", "基金类型": "指数型-股票", "拼音全称": "ZHSHANG"},
            {"基金代码": "005827", "拼音缩写": "YFDLC", "基金简称": "易方达蓝筹精选混合", "基金类型": "混合型-偏股", "拼音全称": "YIFANGDA"},
            {"基金代码": "161903", "拼音缩写": "FZTH", "基金简称": "万家行业优选混合", "基金类型": "混合型-灵活", "拼音全称": "WANJIA"},
            {"基金代码": "519674", "拼音缩写": "YHLJ", "基金简称": "银河沪深300价值ETF联接A", "基金类型": "指数型-股票", "拼音全称": "YINHE"},
            {"基金代码": "000051", "拼音缩写": "HHSY300", "基金简称": "华夏沪深300ETF联接A", "基金类型": "指数型-股票", "拼音全称": "HH300"},
            {"基金代码": "000834", "拼音缩写": "GTQDII", "基金简称": "国泰纳斯达克100", "基金类型": "指数型-海外股票", "拼音全称": "GUOTAI"},
            {"基金代码": "000041", "拼音缩写": "GTGL", "基金简称": "国泰全球绝对收益", "基金类型": "QDII-混合灵活", "拼音全称": "GUOTAIGL"},
            # 应被剔除的
            {"基金代码": "000003", "拼音缩写": "ZHKZ", "基金简称": "中海可转债债券A", "基金类型": "债券型-混合二级", "拼音全称": "ZHONGHAI"},
            {"基金代码": "000009", "拼音缩写": "JXHB", "基金简称": "嘉实货币A", "基金类型": "货币型-普通货币", "拼音全称": "JIASHI"},
            {"基金代码": "000995", "拼音缩写": "FOF1", "基金简称": "华夏聚惠FOF", "基金类型": "FOF-稳健型", "拼音全称": "FOF"},
        ]
    )


@pytest.fixture
def mock_unit_nav_df() -> pd.DataFrame:
    """模拟 单位净值走势 返回。"""
    return pd.DataFrame(
        {
            "净值日期": ["2026-06-01", "2026-06-02", "2026-07-03", "2026-07-04"],
            "单位净值": [1.1000, 1.1050, 1.1200, 1.1234],
            "日增长率": [0.5, 0.45, 0.8, 0.30],
        }
    )


@pytest.fixture
def mock_accum_nav_df() -> pd.DataFrame:
    """模拟 累计净值走势 返回。"""
    return pd.DataFrame(
        {
            "净值日期": ["2026-06-01", "2026-06-02", "2026-07-03", "2026-07-04"],
            "累计净值": [2.1000, 2.1095, 2.1263, 2.1327],
        }
    )


@pytest.fixture
def mock_holdings_df() -> pd.DataFrame:
    """模拟 fund_portfolio_hold_em 返回。"""
    return pd.DataFrame(
        [
            {"序号": 1, "股票代码": "002025", "股票名称": "航天电器", "占净值比例": 3.46, "持股数": 209.92, "持仓市值": 7947.67, "季度": "2024年1季度股票投资明细"},
            {"序号": 2, "股票代码": "600862", "股票名称": "中航高科", "占净值比例": 3.24, "持股数": 380.43, "持仓市值": 7441.16, "季度": "2024年1季度股票投资明细"},
            {"序号": 1, "股票代码": "600941", "股票名称": "中国移动", "占净值比例": 2.86, "持股数": 62.11, "持仓市值": 6568.15, "季度": "2024年2季度股票投资明细"},
        ]
    )


@pytest.fixture
def mock_manager_df() -> pd.DataFrame:
    """模拟 fund_manager_em 返回。"""
    return pd.DataFrame(
        [
            {"序号": 1, "姓名": "王泽实", "所属公司": "华夏基金", "现任基金代码": "000001", "现任基金": "华夏成长混合", "累计从业时间": 3650, "现任基金资产总规模": 27.30, "现任基金最佳回报": 120.5},
            {"序号": 1, "姓名": "侯昊", "所属公司": "招商基金", "现任基金代码": "161725", "现任基金": "招商中证白酒指数", "累计从业时间": 2920, "现任基金资产总规模": 480.0, "现任基金最佳回报": 200.3},
        ]
    )
