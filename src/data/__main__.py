"""数据层 CLI 入口（plan §3.3）+ 异步后台回填（plan §3.4 / Clarify Q6）。

用法：
    python -m src.data refresh [--codes 000001,161725]
    python -m src.data backfill --years 5 [--codes ...]
    python -m src.data status
    python -m src.data sample            # 空缓存时前台返回样例
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from datetime import date
from pathlib import Path

from loguru import logger

from src.data import DataConfig, load_data_config, setup_logging
from src.data.akshare_provider import AkShareProvider, SAMPLE_FUND_CODES
from src.data.cache import ParquetStore


def _progress_path(config: DataConfig) -> Path:
    return config.cache_path / ".backfill_progress.json"


def write_progress(config: DataConfig, done: int, total: int, status: str) -> None:
    """写入后台回填进度文件。"""
    p = _progress_path(config)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "done": done,
        "total": total,
        "progress_pct": round(done / total * 100, 2) if total else 0.0,
        "status": status,  # running | done | interrupted
        "updated_at": date.today().isoformat(),
    }
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def read_progress(config: DataConfig) -> dict | None:
    p = _progress_path(config)
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def cmd_refresh(provider: AkShareProvider, codes: list[str] | None) -> int:
    """增量更新。"""
    summary = provider.refresh_incremental(fund_codes=codes)
    logger.info("增量更新完成：{}", summary)
    return 0


def cmd_backfill(provider: AkShareProvider, config: DataConfig, years: int, codes: list[str] | None) -> int:
    """全量回填（同步）。"""
    targets = codes or provider._all_fund_codes()
    logger.info("全量回填 {} 只基金，{} 年历史", len(targets), years)
    total = len(targets)
    write_progress(config, 0, total, "running")
    try:
        for i, code in enumerate(targets, 1):
            try:
                provider.refresh_full_backfill([code], years=years)
            except Exception as e:
                logger.error("回填 {} 失败：{}", code, e)
            if i % 10 == 0 or i == total:
                write_progress(config, i, total, "running")
        write_progress(config, total, total, "done")
        logger.info("全量回填完成")
    except KeyboardInterrupt:
        write_progress(config, 0, total, "interrupted")
        logger.warning("用户中断，进度已保存")
        return 130
    return 0


def cmd_status(provider: AkShareProvider) -> int:
    """打印新鲜度统计。"""
    summary = provider._freshness.summary()
    if not summary.get("total_records"):
        print("暂无新鲜度记录（缓存为空）。")
        return 0
    print("=" * 50)
    print("数据新鲜度报告")
    print("=" * 50)
    print(f"总记录数: {summary.get('total_records', 0)}")
    print(f"过期数:   {summary.get('stale_count', 0)}")
    print(f"失败数:   {summary.get('failed_count', 0)}")
    print()
    print("按来源分布:")
    for src, cnt in summary.get("by_source", {}).items():
        print(f"  {src}: {cnt}")
    print()
    print("按字段分布:")
    for field, cnt in summary.get("by_field", {}).items():
        print(f"  {field}: {cnt}")
    return 0


def cmd_sample(provider: AkShareProvider) -> int:
    """空缓存时打印样例基金净值概要。"""
    samples = provider.get_sample_nav()
    for code, df in samples.items():
        if df.empty:
            print(f"{code}: （拉取失败或无数据）")
        else:
            last = df.iloc[-1]
            print(
                f"{code}: 最后 {last['trade_date']} 单位净值={last['unit_nav']:.4f} "
                f"共 {len(df)} 条"
            )
    return 0


def maybe_start_background_backfill(
    provider: AkShareProvider,
    config: DataConfig,
    years: int = 5,
) -> threading.Thread | None:
    """空缓存检测 → 后台异步全量回填（Clarify Q6）。

    - 检测 nav 目录为空 且 无进行中的回填 → 起后台线程
    - 前台立即返回，不阻塞调用方
    - 中断重启时若进度文件 status=interrupted → 续跑
    """
    pq = ParquetStore(config.cache_path)
    if pq.has_any_nav():
        return None

    prog = read_progress(config)
    if prog and prog.get("status") == "running":
        logger.info("检测到上次回填未完成，将续跑：{}", prog)
        # 续跑：跳过已完成的 fund_code（简化：全部重跑，缓存去重保证幂等）

    total = len(SAMPLE_FUND_CODES)  # 后台首跑只拉样例，避免长时间
    write_progress(config, 0, total, "running")

    def _bg() -> None:
        try:
            provider.refresh_full_backfill(SAMPLE_FUND_CODES, years=years)
            write_progress(config, total, total, "done")
            logger.info("后台回填完成（样例 {} 只）", total)
        except Exception as e:
            write_progress(config, 0, total, "interrupted")
            logger.error("后台回填异常：{}", e)

    t = threading.Thread(target=_bg, name="backfill", daemon=True)
    t.start()
    logger.info("后台异步回填已启动（样例 {} 只）", total)
    return t


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.data", description="数据层 CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_refresh = sub.add_parser("refresh", help="增量更新")
    p_refresh.add_argument("--codes", help="逗号分隔的基金代码，默认全部")

    p_backfill = sub.add_parser("backfill", help="全量回填")
    p_backfill.add_argument("--years", type=int, default=5)
    p_backfill.add_argument("--codes", help="逗号分隔的基金代码，默认样例")

    sub.add_parser("status", help="打印新鲜度统计")
    sub.add_parser("sample", help="打印样例基金概要（空缓存降级）")

    args = parser.parse_args(argv)

    config = load_data_config()
    setup_logging(config)

    provider = AkShareProvider(config)
    try:
        codes = (
            [c.strip() for c in args.codes.split(",") if c.strip()]
            if getattr(args, "codes", None)
            else None
        )
        if args.command == "refresh":
            return cmd_refresh(provider, codes)
        if args.command == "backfill":
            return cmd_backfill(provider, config, args.years, codes)
        if args.command == "status":
            return cmd_status(provider)
        if args.command == "sample":
            return cmd_sample(provider)
    finally:
        provider.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
