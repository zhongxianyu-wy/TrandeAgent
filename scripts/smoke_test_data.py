"""真实网络烟雾测试（手动执行）。

验证 AkShare 真实接口连通性，拉取 5 只样例基金 30 天数据。
不做断言，只打印结果，用于上线前人工确认。

用法：
    uv run python scripts/smoke_test_data.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta

from src.data import load_data_config, setup_logging
from src.data.akshare_provider import AkShareProvider, SAMPLE_FUND_CODES


def main() -> int:
    config = load_data_config()
    setup_logging(config)

    provider = AkShareProvider(config)
    today = date.today()
    start = today - timedelta(days=30)

    print("=" * 60)
    print("烟雾测试：真实拉取 5 只样例基金 30 天数据")
    print("=" * 60)

    # 1. list_funds（真实全市场）
    try:
        funds = provider.list_funds()
        print(f"[OK] list_funds: 全市场 {len(funds)} 只基金")
        cats = funds["fund_category"].value_counts().to_dict()
        print(f"     大类分布: {cats}")
    except Exception as e:
        print(f"[FAIL] list_funds: {e!r}")
        return 1

    # 2. 每只样例基金净值
    print()
    for code in SAMPLE_FUND_CODES:
        try:
            df = provider.get_nav(code, start, today)
            if df.empty:
                print(f"[WARN] {code}: 无数据")
            else:
                last = df.iloc[-1]
                print(
                    f"[OK] {code}: {len(df)} 条净值，"
                    f"最后 {last['trade_date']} 单位净值={last['unit_nav']:.4f}"
                )
        except Exception as e:
            print(f"[FAIL] {code}: {e!r}")

    # 3. 新鲜度
    print()
    provider._freshness.log_summary()

    provider.close()
    print("\n烟雾测试完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
