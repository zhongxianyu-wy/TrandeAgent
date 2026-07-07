"""Feature #6 fund-analyzer —— 单基金深度分析。

防幻觉三层防御（ADR-005）：
1. Prompt 层：强约束 system prompt，强制【依据：指标名=数值】引用
2. Schema 层：LLM JSON mode 输出结构化报告
3. 代码层：后校验（validator 校验引用指标真实存在且数值一致）

主流程见 DefaultAnalyzer.analyze。
"""
from src.analyzer.analyzer import (
    DefaultAnalyzer,
    FundAnalyzer,
    flatten_metrics,
    label_from_rating,
)
from src.analyzer.config import (
    AnalyzerConfig,
    LLMConfig,
    build_llm_client,
    load_analyzer_config,
)
from src.analyzer.llm import (
    DeepSeekClient,
    LLMClient,
    QwenClient,
    build_user_prompt,
)
from src.analyzer.models import Citation, FundReport, ReportLabel, ReportSection
from src.analyzer.renderer import label_color, render_card, render_markdown
from src.analyzer.validator import (
    CITATION_PATTERN,
    ValidationResult,
    check_citations,
    extract_citations,
)

__all__ = [
    "FundAnalyzer",
    "DefaultAnalyzer",
    "flatten_metrics",
    "label_from_rating",
    "FundReport",
    "ReportSection",
    "Citation",
    "ReportLabel",
    "LLMClient",
    "DeepSeekClient",
    "QwenClient",
    "build_user_prompt",
    "check_citations",
    "extract_citations",
    "ValidationResult",
    "CITATION_PATTERN",
    "render_markdown",
    "render_card",
    "label_color",
    "AnalyzerConfig",
    "LLMConfig",
    "load_analyzer_config",
    "build_llm_client",
]
