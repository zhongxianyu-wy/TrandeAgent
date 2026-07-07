"""fund-analyzer CLI 入口（T12）。

用法：
    python -m src.analyzer analyze --code 000001
    python -m src.analyzer analyze --code 000001 --provider qwen --markdown
    python -m src.analyzer batch            # 分析配置文件中的全部基金
"""
from __future__ import annotations

import argparse
import sys

from loguru import logger

from src.analyzer.analyzer import DefaultAnalyzer
from src.analyzer.config import LLMConfig, build_llm_client, load_analyzer_config
from src.analyzer.renderer import render_markdown


def _build_default_analyzer(provider: str | None = None) -> DefaultAnalyzer:
    """组装默认 analyzer（真实数据 + 真实/配置 LLM）。"""
    from datetime import date

    from src.data.akshare_provider import AkShareProvider
    from src.data.config import load_data_config
    from src.indicators.default_engine import DefaultIndicatorEngine

    config = load_analyzer_config()
    llm_config = config.llm
    if provider:
        llm_config = LLMConfig(
            provider=provider,  # type: ignore[arg-type]
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
            model=llm_config.model,
            timeout=llm_config.timeout,
        )
    llm = build_llm_client(config, llm_config=llm_config)

    data_config = load_data_config()
    provider_obj = AkShareProvider(data_config)
    engine = DefaultIndicatorEngine(provider_obj)
    return DefaultAnalyzer(
        engine=engine,
        llm=llm,
        years=config.years,
        max_retries=config.max_retries,
    )


def cmd_analyze(args: argparse.Namespace) -> int:
    analyzer = _build_default_analyzer(args.provider)
    report = analyzer.analyze(args.code)
    md = render_markdown(report)
    if args.markdown:
        print(md)
    else:
        logger.info("分析完成：{} 标签={} 降级={}", args.code, report.label, report.degraded)
        print(md)
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    config = load_analyzer_config()
    codes = config.funds
    if not codes:
        logger.warning("配置文件未指定 funds，无可分析基金")
        return 1
    analyzer = _build_default_analyzer(args.provider)
    for code in codes:
        report = analyzer.analyze(code)
        print(render_markdown(report))
        print("\n" + "=" * 60 + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="src.analyzer", description="单基金深度分析")
    sub = parser.add_subparsers(dest="command", required=True)

    p_analyze = sub.add_parser("analyze", help="分析单只基金")
    p_analyze.add_argument("--code", required=True, help="基金代码")
    p_analyze.add_argument(
        "--provider", choices=["deepseek", "qwen"], default=None, help="LLM provider"
    )
    p_analyze.add_argument("--markdown", action="store_true", help="输出 Markdown")
    p_analyze.set_defaults(func=cmd_analyze)

    p_batch = sub.add_parser("batch", help="分析配置文件中的全部基金")
    p_batch.add_argument(
        "--provider", choices=["deepseek", "qwen"], default=None, help="LLM provider"
    )
    p_batch.set_defaults(func=cmd_batch)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
