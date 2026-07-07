"""业务编排主入口 - 串联所有业务模块的每日流水线。

被 scheduler（Feature #3 launchd）调用，对应 spec §3 FR-1：
    python -m src.main daily          # 每日主流程（仅交易日）
    python -m src.main daily --force  # 强制运行（忽略交易日过滤）
    python -m src.main daily --dry-run # 模拟运行，不推送飞书
    python -m src.main status         # 查看最近运行状态

每日流水线顺序（单步失败不阻断整体，标记为 partial）：
    1. 交易日判定（非交易日直接 return）
    2. 数据刷新（DataProvider.refresh_incremental）
    3. 指标批量计算（IndicatorEngine.calc_batch）
    4. 基金筛选（FundScreener.screen）
    5. 信号计算（SignalEngine.calc_signals，针对观察池）
    6. LLM 分析报告（FundAnalyzer.analyze，针对 Top-N）
    7. 推送飞书（FeishuClient.send_card）
    8. 记录运行状态（StateStore.record）
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from loguru import logger

# 状态存储默认路径（与 scheduler state.py 对齐）
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE_DIR = PROJECT_ROOT / "data" / "state"
LAST_RUN_FILE = DEFAULT_STATE_DIR / "last_run.json"
RUN_HISTORY_FILE = DEFAULT_STATE_DIR / "run_history.jsonl"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class DailyContext:
    """单次每日运行的上下文，在各步骤间传递中间结果。

    Attributes:
        run_date: 运行日期。
        mode: 运行模式标识（daily / force / dry_run）。
        force: 是否强制运行（忽略交易日过滤）。
        dry_run: 是否模拟运行（不推送飞书）。
        steps_result: 每个步骤的执行结果 {step_name: {status, ...}}。
        indicators_df: 指标批量计算结果（步骤 3 产物）。
        candidates_df: 筛选结果（步骤 4 产物）。
        observation_codes: 观察池基金代码列表。
        top_candidates: 待分析的 Top-N 基金代码列表。
        signals: 信号计算结果。
        cards_to_send: 待推送的飞书卡片列表。
    """

    run_date: date
    mode: str = "daily"
    force: bool = False
    dry_run: bool = False
    steps_result: dict[str, dict[str, Any]] = field(default_factory=dict)
    indicators_df: Any = None
    candidates_df: Any = None
    observation_codes: list[str] = field(default_factory=list)
    top_candidates: list[str] = field(default_factory=list)
    signals: list[Any] = field(default_factory=list)
    cards_to_send: list[dict] = field(default_factory=list)

    def overall_status(self) -> str:
        """根据各步骤结果汇总整体状态。

        全部 success → success；全部 failed → failed；混合 → partial。
        """
        # 仅检查步骤结果（dict 类型），跳过 _duration_sec 等元数据
        step_statuses = [
            s.get("status")
            for s in self.steps_result.values()
            if isinstance(s, dict)
        ]
        if not step_statuses:
            return "success"
        statuses = step_statuses
        if all(s == "success" or s == "skipped" for s in statuses):
            return "success"
        if all(s == "failed" for s in statuses):
            return "failed"
        return "partial"


# ---------------------------------------------------------------------------
# 每日流水线
# ---------------------------------------------------------------------------
class DailyPipeline:
    """每日主流程编排器。

    默认惰性初始化各业务模块依赖（首次访问时创建）；
    测试中可直接覆盖 ``.provider`` / ``.engine`` 等属性注入 mock。
    """

    def __init__(self) -> None:
        # 惰性依赖（首次访问时初始化，测试中可覆盖）
        self._provider = None
        self._engine = None
        self._screener = None
        self._signal_engine = None
        self._analyzer = None
        self._feishu = None
        self._state_store = None

    # ---- 依赖惰性初始化 ----
    @property
    def provider(self):
        if self._provider is None:
            self._provider = self._init_provider()
        return self._provider

    @provider.setter
    def provider(self, v):
        self._provider = v

    def _init_provider(self):
        from src.data import load_data_config, setup_logging
        from src.data.akshare_provider import AkShareProvider

        config = load_data_config()
        setup_logging(config)
        return AkShareProvider(config)

    @property
    def engine(self):
        if self._engine is None:
            self._engine = self._init_engine()
        return self._engine

    @engine.setter
    def engine(self, v):
        self._engine = v

    def _init_engine(self):
        from src.indicators.default_engine import DefaultIndicatorEngine

        return DefaultIndicatorEngine(self.provider)

    @property
    def screener(self):
        if self._screener is None:
            from src.screener.engine import DefaultScreener

            self._screener = DefaultScreener()
        return self._screener

    @screener.setter
    def screener(self, v):
        self._screener = v

    @property
    def signal_engine(self):
        if self._signal_engine is None:
            from src.signal.engine import DefaultSignalEngine

            self._signal_engine = DefaultSignalEngine(self.provider)
        return self._signal_engine

    @signal_engine.setter
    def signal_engine(self, v):
        self._signal_engine = v

    @property
    def analyzer(self):
        if self._analyzer is None:
            self._analyzer = self._init_analyzer()
        return self._analyzer

    @analyzer.setter
    def analyzer(self, v):
        self._analyzer = v

    def _init_analyzer(self):
        from src.analyzer.analyzer import DefaultAnalyzer
        from src.analyzer.llm import LLMClient

        return DefaultAnalyzer(self.engine, LLMClient())

    @property
    def feishu(self):
        if self._feishu is None:
            self._feishu = self._init_feishu()
        return self._feishu

    @feishu.setter
    def feishu(self, v):
        self._feishu = v

    def _init_feishu(self):
        from src.feishu.lark_cli_client import LarkCliClient

        return LarkCliClient()

    @property
    def state_store(self):
        if self._state_store is None:
            from src.scheduler.state import StateStore

            DEFAULT_STATE_DIR.mkdir(parents=True, exist_ok=True)
            self._state_store = StateStore(LAST_RUN_FILE, RUN_HISTORY_FILE)
        return self._state_store

    @state_store.setter
    def state_store(self, v):
        self._state_store = v

    # ---- 交易日判定 ----
    def should_run(self, run_date: date, force: bool) -> bool:
        """判定是否应执行每日流程（FR-2）。

        force=True 跳过交易日过滤；否则用 chinese_calendar 判定。
        """
        if force:
            return True
        from src.scheduler.holiday import is_trading_day

        return is_trading_day(run_date)

    # ---- 观察池加载 ----
    def _load_observation_codes(self) -> list[str]:
        """从飞书 Base 查询观察池基金代码列表。

        失败时返回空列表（不阻断流程）。
        """
        try:
            records = self.feishu.query_records("观察池")
            return [
                r.get("fund_code", r.get("基金代码", ""))
                for r in records
                if r.get("fund_code") or r.get("基金代码")
            ]
        except Exception as e:  # noqa: BLE001
            logger.warning("加载观察池失败，使用空列表：{}", e)
            return []

    # ---- 单步骤封装 ----
    def _run_step(self, step_name: str, ctx: DailyContext, fn) -> None:
        """执行单步骤，捕获异常写入 steps_result（不抛出）。"""
        try:
            fn(ctx)
        except Exception as e:  # noqa: BLE001
            logger.error("步骤 {} 失败：{}", step_name, e)
            ctx.steps_result[step_name] = {
                "status": "failed",
                "error": str(e),
            }

    def step_refresh_data(self, ctx: DailyContext) -> None:
        """步骤 2：增量刷新数据（dry_run 时跳过，避免真实网络副作用）。"""
        if ctx.dry_run:
            ctx.steps_result["refresh_data"] = {
                "status": "skipped",
                "reason": "dry_run",
            }
            logger.info("dry-run 模式，跳过数据刷新")
            return

        summary = self.provider.refresh_incremental()
        ctx.steps_result["refresh_data"] = {
            "status": "success",
            "summary": summary,
        }
        logger.info("数据刷新完成：{}", summary)

    def step_calc_indicators(self, ctx: DailyContext) -> None:
        """步骤 3：批量计算指标。"""
        import pandas as pd

        funds_df = self.provider.list_funds()
        if funds_df is None or funds_df.empty:
            ctx.indicators_df = pd.DataFrame()
            ctx.steps_result["calc_indicators"] = {
                "status": "success",
                "fund_count": 0,
            }
            return

        codes = funds_df["fund_code"].tolist()
        indicators_df = self.engine.calc_batch(codes, ctx.run_date)
        ctx.indicators_df = indicators_df
        ctx.steps_result["calc_indicators"] = {
            "status": "success",
            "fund_count": len(codes),
        }
        logger.info("指标计算完成：{} 只基金", len(codes))

    def step_screen_funds(self, ctx: DailyContext) -> None:
        """步骤 4：筛选 Top-N 候选基金。"""
        from src.screener.presets import get_preset

        if ctx.indicators_df is None or ctx.indicators_df.empty:
            ctx.candidates_df = ctx.indicators_df
            ctx.steps_result["screen_funds"] = {
                "status": "success",
                "candidate_count": 0,
            }
            return

        config = get_preset("rule_4433")
        candidates = self.screener.screen(config, ctx.indicators_df)
        ctx.candidates_df = candidates
        ctx.top_candidates = (
            candidates["fund_code"].tolist() if not candidates.empty else []
        )
        ctx.steps_result["screen_funds"] = {
            "status": "success",
            "candidate_count": len(ctx.top_candidates),
        }
        logger.info("筛选完成：{} 只候选", len(ctx.top_candidates))

    def step_calc_signals(self, ctx: DailyContext) -> None:
        """步骤 5：计算观察池基金的择时信号。"""
        from src.signal.__main__ import load_rules

        ctx.observation_codes = self._load_observation_codes()
        if not ctx.observation_codes:
            ctx.steps_result["calc_signals"] = {
                "status": "success",
                "signal_count": 0,
            }
            logger.info("观察池为空，跳过信号计算")
            return

        rules, _ = load_rules()
        signals = self.signal_engine.calc_signals(
            ctx.observation_codes, rules, end_date=ctx.run_date
        )
        ctx.signals = signals
        ctx.steps_result["calc_signals"] = {
            "status": "success",
            "signal_count": len(signals),
        }
        logger.info("信号计算完成：{} 条", len(signals))

    def step_analyze_top_funds(self, ctx: DailyContext) -> None:
        """步骤 6：对 Top-N 候选生成 LLM 分析报告（dry_run 时跳过，避免真实 LLM 调用）。"""
        if ctx.dry_run:
            ctx.steps_result["analyze_reports"] = {
                "status": "skipped",
                "reason": "dry_run",
                "report_count": 0,
            }
            logger.info("dry-run 模式，跳过 LLM 分析")
            return

        if not ctx.top_candidates:
            ctx.steps_result["analyze_reports"] = {
                "status": "success",
                "report_count": 0,
            }
            return

        cards: list[dict] = []
        analyzed = 0
        for code in ctx.top_candidates:
            try:
                report = self.analyzer.analyze(code)
                card = self.analyzer.render_card(report)
                cards.append(card)
                analyzed += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("基金 {} 分析失败：{}", code, e)

        ctx.cards_to_send.extend(cards)
        ctx.steps_result["analyze_reports"] = {
            "status": "success",
            "report_count": analyzed,
        }
        logger.info("LLM 分析完成：{}/{} 成功", analyzed, len(ctx.top_candidates))

    def step_push_feishu(self, ctx: DailyContext) -> None:
        """步骤 7：推送飞书卡片（dry_run 时跳过）。"""
        if ctx.dry_run:
            ctx.steps_result["push_feishu"] = {
                "status": "skipped",
                "reason": "dry_run",
                "card_count": len(ctx.cards_to_send),
            }
            logger.info("dry-run 模式，跳过推送 {} 张卡片", len(ctx.cards_to_send))
            return

        sent = 0
        for card in ctx.cards_to_send:
            try:
                self.feishu.send_card(card)
                sent += 1
            except Exception as e:  # noqa: BLE001
                logger.warning("推送卡片失败：{}", e)

        ctx.steps_result["push_feishu"] = {
            "status": "success",
            "sent_count": sent,
        }
        logger.info("飞书推送完成：{}/{} 成功", sent, len(ctx.cards_to_send))

    def step_record_state(self, ctx: DailyContext) -> None:
        """步骤 8：记录运行状态。"""
        status = ctx.overall_status()
        self.state_store.record(
            status=status,
            duration_sec=ctx.steps_result.get("_duration_sec", 0),
            mode=ctx.mode,
            fund_count=ctx.steps_result.get("calc_indicators", {}).get(
                "fund_count"
            ),
        )
        ctx.steps_result["record_state"] = {"status": "success"}
        logger.info("运行状态已记录：{}", status)

    # ---- 主入口 ----
    def run_daily(self, force: bool = False, dry_run: bool = False) -> dict:
        """执行完整的每日流水线。

        Args:
            force: 强制运行（忽略交易日过滤）。
            dry_run: 模拟运行（不推送飞书）。

        Returns:
            运行结果摘要 dict：{status, run_date, steps, duration_sec}
        """
        run_date = date.today()
        mode = "force" if force else ("dry_run" if dry_run else "daily")

        # 步骤 1：交易日判定
        if not self.should_run(run_date, force):
            logger.info("{} 非交易日，跳过每日流程", run_date)
            return {"status": "skipped", "run_date": str(run_date)}

        logger.info("=== 每日流水线启动 === date={} mode={}", run_date, mode)
        start_ts = time.time()

        ctx = DailyContext(run_date=run_date, mode=mode, force=force, dry_run=dry_run)

        # 步骤 2-8 顺序执行（单步失败不阻断）
        self._run_step("refresh_data", ctx, self.step_refresh_data)
        self._run_step("calc_indicators", ctx, self.step_calc_indicators)
        self._run_step("screen_funds", ctx, self.step_screen_funds)
        self._run_step("calc_signals", ctx, self.step_calc_signals)
        self._run_step("analyze_reports", ctx, self.step_analyze_top_funds)
        self._run_step("push_feishu", ctx, self.step_push_feishu)

        duration = int(time.time() - start_ts)
        ctx.steps_result["_duration_sec"] = duration
        self._run_step("record_state", ctx, self.step_record_state)

        status = ctx.overall_status()
        logger.info(
            "=== 每日流水线完成 === status={} duration={}s steps={}",
            status,
            duration,
            {k: v.get("status") for k, v in ctx.steps_result.items() if isinstance(v, dict)},
        )

        return {
            "status": status,
            "run_date": str(run_date),
            "duration_sec": duration,
            "steps": {k: v.get("status") for k, v in ctx.steps_result.items() if isinstance(v, dict)},
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """构建 CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="src.main",
        description="TrandeAgent 每日流水线编排入口",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_daily = sub.add_parser("daily", help="执行每日流水线")
    p_daily.add_argument(
        "--force", action="store_true", help="强制运行（忽略交易日过滤）"
    )
    p_daily.add_argument(
        "--dry-run",
        action="store_true",
        help="模拟运行，不推送飞书",
    )

    sub.add_parser("status", help="查看最近运行状态")

    return parser


def cmd_status() -> int:
    """查看最近运行状态。"""
    pipeline = DailyPipeline()
    try:
        last_run = pipeline.state_store.load_last_run()
        if last_run is None:
            print("暂无运行记录")
        else:
            print("最近一次运行：")
            for k, v in last_run.items():
                print(f"  {k}: {v}")
    except Exception as e:  # noqa: BLE001
        logger.warning("读取状态失败：{}", e)
        print(f"读取状态失败：{e}")
    return 0


def cmd_daily(force: bool, dry_run: bool) -> int:
    """执行每日流水线。"""
    pipeline = DailyPipeline()
    result = pipeline.run_daily(force=force, dry_run=dry_run)
    print(f"运行结果：{result['status']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI 主入口。"""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "daily":
        return cmd_daily(force=args.force, dry_run=args.dry_run)
    if args.command == "status":
        return cmd_status()
    return 0


if __name__ == "__main__":
    sys.exit(main())
