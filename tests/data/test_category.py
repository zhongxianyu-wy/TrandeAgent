"""T11: category 4 类过滤测试（classify_category）。

基于 fund_name_em 真实类型分布设计用例。
"""
from __future__ import annotations

import pytest

from src.data.akshare_provider import classify_category


@pytest.mark.parametrize(
    "fund_type,fund_name,expected",
    [
        # active_stock
        ("混合型-偏股", "华夏成长混合", "active_stock"),
        ("混合型-灵活", "万家行业优选混合", "active_stock"),
        ("股票型", "某纯股票基金", "active_stock"),
        ("混合型-平衡", "某平衡混合", "active_stock"),
        ("混合型-绝对收益", "某绝对收益", "active_stock"),
        # index
        ("指数型-股票", "招商中证白酒指数", "index"),
        ("指数型-其他", "某其他指数", "index"),
        # etf_link（名称识别）
        ("指数型-股票", "银河沪深300价值ETF联接A", "etf_link"),
        # qdii（股票类）
        ("指数型-海外股票", "国泰纳斯达克100", "qdii"),
        ("QDII-普通股票", "某QDII股票", "qdii"),
        ("QDII-混合偏股", "某QDII偏股", "qdii"),
        # 剔除
        ("债券型-长债", "某长债", None),
        ("债券型-混合二级", "中海可转债", None),
        ("货币型-普通货币", "嘉实货币A", None),
        ("FOF-稳健型", "某FOF", None),
        ("Reits", "某REIT", None),
        ("商品", "某商品基金", None),
        ("指数型-固收", "某固收指数", None),
        ("QDII-纯债", "某QDII债", None),
        ("QDII-商品", "某QDII商品", None),
        ("QDII-FOF", "某QDII FOF", None),
        ("", "空类型", None),
    ],
)
def test_classify_category(fund_type, fund_name, expected):
    assert classify_category(fund_type, fund_name) == expected


def test_classify_excludes_debt_and_money():
    """AC-4: 列表不含债基/货基。"""
    types = [
        ("债券型-长债", "债"),
        ("货币型-普通货币", "货"),
        ("FOF-进取型", "FOF"),
        ("Reits", "REIT"),
    ]
    for ft, fn in types:
        assert classify_category(ft, fn) is None


def test_classify_covers_four_categories():
    """4 大类都有样本命中。"""
    got = {
        classify_category("混合型-偏股", "x"),
        classify_category("指数型-股票", "y"),
        classify_category("指数型-股票", "zETF联接A"),
        classify_category("QDII-普通股票", "w"),
    }
    assert got == {"active_stock", "index", "etf_link", "qdii"}
