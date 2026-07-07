"""业务编排主入口 main.py 的单元测试。

覆盖：
- 交易日判定（FR-2）
- daily 流程串联（数据→指标→筛选→信号→分析→推送→记录）
- --force / --dry-run 参数（FR-4）
- 单步失败不影响整体（partial）
- CLI 参数解析
"""
from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.main import (
    DailyContext,
    DailyPipeline,
    build_parser,
    main,
)


@pytest.fixture
def tmp_state_files(tmp_path: Path) -> tuple[Path, Path]:
    """临时状态文件路径。"""
    last_run = tmp_path / "state" / "last_run.json"
    history = tmp_path / "state" / "run_history.jsonl"
    return last_run, history


class TestDailyContext:
    """DailyContext 数据结构测试。"""

    def test_context_creation(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        assert ctx.run_date == date(2026, 7, 7)
        assert ctx.mode == "daily"
        assert ctx.force is False
        assert ctx.dry_run is False
        assert ctx.steps_result == {}

    def test_context_force_mode(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily", force=True)
        assert ctx.force is True

    def test_record_step(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result["refresh_data"] = {"status": "success", "fund_count": 100}
        assert ctx.steps_result["refresh_data"]["fund_count"] == 100

    def test_overall_status_all_success(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result = {"a": {"status": "success"}, "b": {"status": "success"}}
        assert ctx.overall_status() == "success"

    def test_overall_status_with_skipped(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result = {"a": {"status": "success"}, "b": {"status": "skipped"}}
        assert ctx.overall_status() == "success"

    def test_overall_status_partial(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result = {"a": {"status": "success"}, "b": {"status": "failed"}}
        assert ctx.overall_status() == "partial"

    def test_overall_status_all_failed(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result = {"a": {"status": "failed"}, "b": {"status": "failed"}}
        assert ctx.overall_status() == "failed"

    def test_overall_status_empty(self):
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        assert ctx.overall_status() == "success"


class TestTradingDayCheck:
    """交易日判定测试（FR-2）。"""

    def test_skip_non_trading_day_weekend(self):
        """周末（2026-07-04 周六）非交易日，应跳过。"""
        pipeline = DailyPipeline()
        with patch("src.scheduler.holiday.is_trading_day", return_value=False):
            result = pipeline.should_run(date(2026, 7, 4), force=False)
        assert result is False

    def test_force_overrides_non_trading_day(self):
        """--force 强制运行，即使是周末。"""
        pipeline = DailyPipeline()
        result = pipeline.should_run(date(2026, 7, 4), force=True)
        assert result is True

    @patch("src.scheduler.holiday.is_trading_day")
    def test_trading_day_passes(self, mock_is_trading):
        mock_is_trading.return_value = True
        pipeline = DailyPipeline()
        result = pipeline.should_run(date(2026, 7, 7), force=False)
        assert result is True

    @patch("src.scheduler.holiday.is_trading_day")
    def test_holiday_skipped(self, mock_is_trading):
        """节假日非交易日，应跳过。"""
        mock_is_trading.return_value = False
        pipeline = DailyPipeline()
        result = pipeline.should_run(date(2026, 10, 1), force=False)
        assert result is False


@pytest.fixture
def pipeline_with_mocks():
    """构建注入 mock 依赖的 pipeline（避免惰性初始化触发真实网络）。"""
    pipeline = DailyPipeline()
    pipeline.provider = MagicMock()
    pipeline.engine = MagicMock()
    pipeline.screener = MagicMock()
    pipeline.signal_engine = MagicMock()
    pipeline.analyzer = MagicMock()
    pipeline.feishu = MagicMock()
    pipeline.state_store = MagicMock()
    # feishu.query_records 默认返回空列表（观察池）
    pipeline.feishu.query_records.return_value = []
    return pipeline


class TestDailyPipelineSteps:
    """DailyPipeline 各步骤测试（mock 依赖）。"""

    def test_step_refresh_data_success(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        p.provider.refresh_incremental.return_value = {"updated": 100}
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        p.step_refresh_data(ctx)
        assert ctx.steps_result["refresh_data"]["status"] == "success"
        p.provider.refresh_incremental.assert_called_once()

    def test_step_refresh_data_failure_continues(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        p.provider.refresh_incremental.side_effect = RuntimeError("network error")
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        p._run_step("refresh_data", ctx, p.step_refresh_data)
        assert ctx.steps_result["refresh_data"]["status"] == "failed"
        assert "network error" in ctx.steps_result["refresh_data"]["error"]

    def test_step_calc_indicators_success(self, pipeline_with_mocks):
        import pandas as pd
        p = pipeline_with_mocks
        p.provider.list_funds.return_value = pd.DataFrame(
            {"fund_code": ["000001", "161725"]}
        )
        p.engine.calc_batch.return_value = pd.DataFrame(
            {"fund_code": ["000001", "161725"], "rating": [5, 4]}
        )
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        p.step_calc_indicators(ctx)
        assert ctx.steps_result["calc_indicators"]["status"] == "success"
        assert ctx.steps_result["calc_indicators"]["fund_count"] == 2

    def test_step_calc_indicators_empty(self, pipeline_with_mocks):
        import pandas as pd
        p = pipeline_with_mocks
        p.provider.list_funds.return_value = pd.DataFrame()
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        p.step_calc_indicators(ctx)
        assert ctx.steps_result["calc_indicators"]["status"] == "success"
        assert ctx.steps_result["calc_indicators"]["fund_count"] == 0

    def test_step_screen_funds_success(self, pipeline_with_mocks):
        import pandas as pd
        p = pipeline_with_mocks
        p.screener.screen.return_value = pd.DataFrame(
            {"fund_code": ["000001"], "score": [3.5]}
        )
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.indicators_df = pd.DataFrame({"fund_code": ["000001"]})
        p.step_screen_funds(ctx)
        assert ctx.steps_result["screen_funds"]["status"] == "success"
        assert ctx.top_candidates == ["000001"]

    def test_step_screen_funds_empty_indicators(self, pipeline_with_mocks):
        import pandas as pd
        p = pipeline_with_mocks
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.indicators_df = pd.DataFrame()
        p.step_screen_funds(ctx)
        assert ctx.steps_result["screen_funds"]["status"] == "success"
        assert ctx.steps_result["screen_funds"]["candidate_count"] == 0

    def test_step_calc_signals_success(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        p.signal_engine.calc_signals.return_value = []
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.observation_codes = ["000001"]
        p.step_calc_signals(ctx)
        assert ctx.steps_result["calc_signals"]["status"] == "success"

    def test_step_calc_signals_empty_pool(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        p.feishu.query_records.return_value = []
        p.step_calc_signals(ctx)
        assert ctx.steps_result["calc_signals"]["status"] == "success"
        assert ctx.steps_result["calc_signals"]["signal_count"] == 0

    def test_step_analyze_top_funds_success(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        p.analyzer.analyze.return_value = MagicMock()
        p.analyzer.render_card.return_value = {"type": "card"}
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.top_candidates = ["000001"]
        p.step_analyze_top_funds(ctx)
        assert ctx.steps_result["analyze_reports"]["status"] == "success"
        assert len(ctx.cards_to_send) == 1

    def test_step_analyze_top_funds_empty(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.top_candidates = []
        p.step_analyze_top_funds(ctx)
        assert ctx.steps_result["analyze_reports"]["status"] == "success"
        assert ctx.steps_result["analyze_reports"]["report_count"] == 0

    def test_step_push_feishu_dry_run_skips(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily", dry_run=True)
        ctx.cards_to_send = [{"type": "card"}]
        p.step_push_feishu(ctx)
        assert ctx.steps_result["push_feishu"]["status"] == "skipped"
        p.feishu.send_card.assert_not_called()

    def test_step_push_feishu_success(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        p.feishu.send_card.return_value = "msg_001"
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.cards_to_send = [{"type": "card"}]
        p.step_push_feishu(ctx)
        assert ctx.steps_result["push_feishu"]["status"] == "success"
        p.feishu.send_card.assert_called_once()

    def test_step_record_state_always_runs(self, pipeline_with_mocks):
        p = pipeline_with_mocks
        ctx = DailyContext(run_date=date(2026, 7, 7), mode="daily")
        ctx.steps_result = {"refresh_data": {"status": "success"}}
        p.step_record_state(ctx)
        assert ctx.steps_result["record_state"]["status"] == "success"
        p.state_store.record.assert_called_once()


class TestDailyPipelineFullRun:
    """daily 全流程集成测试（mock 依赖）。"""

    def test_full_daily_run_success(self):
        """完整的 daily 流程，所有步骤成功。"""
        import pandas as pd
        pipeline = DailyPipeline()
        pipeline.provider = MagicMock()
        pipeline.engine = MagicMock()
        pipeline.screener = MagicMock()
        pipeline.signal_engine = MagicMock()
        pipeline.analyzer = MagicMock()
        pipeline.feishu = MagicMock()
        pipeline.state_store = MagicMock()
        pipeline.feishu.query_records.return_value = []

        pipeline.provider.refresh_incremental.return_value = {"updated": 10}
        pipeline.provider.list_funds.return_value = pd.DataFrame(
            {"fund_code": ["000001"]}
        )
        pipeline.engine.calc_batch.return_value = pd.DataFrame(
            {"fund_code": ["000001"], "rating": [5]}
        )
        pipeline.screener.screen.return_value = pd.DataFrame(
            {"fund_code": ["000001"], "score": [3.0]}
        )
        pipeline.signal_engine.calc_signals.return_value = []
        pipeline.analyzer.analyze.return_value = MagicMock()
        pipeline.analyzer.render_card.return_value = {"type": "card"}
        pipeline.feishu.send_card.return_value = "msg_001"

        result = pipeline.run_daily(force=True, dry_run=False)

        assert result["status"] == "success"
        pipeline.feishu.send_card.assert_called()

    def test_dry_run_no_push(self):
        """--dry-run 不推送飞书。"""
        import pandas as pd
        pipeline = DailyPipeline()
        pipeline.provider = MagicMock()
        pipeline.engine = MagicMock()
        pipeline.screener = MagicMock()
        pipeline.signal_engine = MagicMock()
        pipeline.analyzer = MagicMock()
        pipeline.feishu = MagicMock()
        pipeline.state_store = MagicMock()
        pipeline.feishu.query_records.return_value = []

        pipeline.provider.refresh_incremental.return_value = {}
        pipeline.provider.list_funds.return_value = pd.DataFrame()
        pipeline.engine.calc_batch.return_value = pd.DataFrame()
        pipeline.screener.screen.return_value = pd.DataFrame()
        pipeline.signal_engine.calc_signals.return_value = []

        pipeline.run_daily(force=True, dry_run=True)

        pipeline.feishu.send_card.assert_not_called()

    @patch("src.scheduler.holiday.is_trading_day", return_value=False)
    def test_non_trading_day_returns_early(self, _mock):
        """非交易日（无 force）直接返回。"""
        pipeline = DailyPipeline()
        pipeline.provider = MagicMock()
        result = pipeline.run_daily(force=False, dry_run=False)
        pipeline.provider.refresh_incremental.assert_not_called()
        assert result["status"] == "skipped"

    def test_partial_failure_continues(self):
        """某步骤失败不阻断后续步骤。"""
        import pandas as pd
        pipeline = DailyPipeline()
        pipeline.provider = MagicMock()
        pipeline.engine = MagicMock()
        pipeline.screener = MagicMock()
        pipeline.signal_engine = MagicMock()
        pipeline.analyzer = MagicMock()
        pipeline.feishu = MagicMock()
        pipeline.state_store = MagicMock()
        pipeline.feishu.query_records.return_value = []

        pipeline.provider.refresh_incremental.side_effect = RuntimeError("net")
        pipeline.provider.list_funds.return_value = pd.DataFrame(
            {"fund_code": ["000001"]}
        )
        pipeline.engine.calc_batch.return_value = pd.DataFrame(
            {"fund_code": ["000001"]}
        )
        pipeline.screener.screen.return_value = pd.DataFrame()
        pipeline.signal_engine.calc_signals.return_value = []

        result = pipeline.run_daily(force=True, dry_run=True)
        assert result["status"] == "partial"


class TestCLI:
    """CLI 参数解析测试。"""

    def test_parser_daily(self):
        parser = build_parser()
        args = parser.parse_args(["daily"])
        assert args.command == "daily"
        assert args.force is False
        assert args.dry_run is False

    def test_parser_daily_force(self):
        parser = build_parser()
        args = parser.parse_args(["daily", "--force"])
        assert args.force is True

    def test_parser_daily_dry_run(self):
        parser = build_parser()
        args = parser.parse_args(["daily", "--dry-run"])
        assert args.dry_run is True

    def test_parser_status(self):
        parser = build_parser()
        args = parser.parse_args(["status"])
        assert args.command == "status"

    @patch("src.scheduler.holiday.is_trading_day", return_value=False)
    def test_main_daily_skipped(self, _mock):
        """main 函数在非交易日返回 0（skipped）。"""
        rc = main(["daily"])
        assert rc == 0

    @patch("src.main.DailyPipeline")
    def test_main_status(self, mock_pipeline_cls):
        """status 命令正常运行。"""
        mock_pipeline = MagicMock()
        mock_pipeline.state_store.load_last_run.return_value = None
        mock_pipeline_cls.return_value = mock_pipeline
        rc = main(["status"])
        assert rc == 0
