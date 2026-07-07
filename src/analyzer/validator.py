"""后校验（T07 / ADR-005 第三层防御）。

解析报告中所有【依据：指标名=数值】引用，验证：
1. 指标名确实存在于输入 metrics（拦截编造指标）
2. 数值与 metrics 中的真实值一致（拦截数值幻觉，误差容忍百分比/小数两种写法）

任一引用不通过 → 视为幻觉，触发重试/降级。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from src.analyzer.models import FundReport

# 【依据：指标名=数值】或【依据:指标名=数值】（中英文冒号兼容）
CITATION_PATTERN = re.compile(r"【依据\s*[:：]\s*([^=【】]+?)\s*=\s*([^【】]+?)】")

# 数值提取（含负号、小数、千分位逗号）
_NUMBER_PATTERN = re.compile(r"-?\d[\d,]*\.?\d*")

# 数值一致性容忍
_ABS_TOL = 0.002  # 小数形式绝对误差
_PCT_TOL = 0.1  # 百分比形式误差（0.1 个百分点）


@dataclass
class ValidationResult:
    """后校验结果。"""

    valid: bool
    errors: list[str] = field(default_factory=list)
    citations_checked: int = 0
    hallucinated_metrics: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.valid


def extract_citations(text: str) -> list[tuple[str, str]]:
    """从文本中提取所有 (指标名, 数值文本) 引用。"""
    return [(m.group(1).strip(), m.group(2).strip()) for m in CITATION_PATTERN.finditer(text)]


def _extract_number(s: str) -> float | None:
    """从字符串中提取首个数值（支持负数/小数/千分位）。"""
    m = _NUMBER_PATTERN.search(s)
    if not m:
        return None
    try:
        return float(m.group(0).replace(",", ""))
    except ValueError:
        return None


def _values_match(cited_raw: str, actual: float) -> bool:
    """判断引用数值是否与真实值一致（兼容 0.152 与 15.2% 两种写法）。"""
    n = _extract_number(cited_raw)
    if n is None:
        return False
    # 小数形式直接比对
    if abs(n - actual) < _ABS_TOL:
        return True
    # 百分比形式：真实值 0.152 → 15.2
    if abs(n - actual * 100.0) < _PCT_TOL:
        return True
    return False


def check_citations(report: FundReport, metrics: dict) -> ValidationResult:
    """校验报告中所有引用。

    Args:
        report: 待校验报告。
        metrics: 输入指标 dict（指标名 → 真实值）。

    Returns:
        ValidationResult，valid=False 表示检测到幻觉或未遵守引用规则。
    """
    errors: list[str] = []
    hallucinated: list[str] = []
    checked = 0

    # 扫描一句话结论 + 各章节
    texts: list[tuple[str, str]] = [(report.one_liner, "一句话结论")]
    for section in report.sections:
        texts.append((section.content, section.title))

    for text, location in texts:
        for name, val in extract_citations(text):
            checked += 1
            if name not in metrics:
                hallucinated.append(name)
                errors.append(f"[{location}] 编造指标：{name}（不在输入指标中）")
                continue
            actual = metrics[name]
            if isinstance(actual, str):
                if val.strip() != actual.strip():
                    errors.append(
                        f"[{location}] 数值不一致：{name}={val}（应为 {actual}）"
                    )
            else:
                try:
                    actual_f = float(actual)
                except (TypeError, ValueError):
                    errors.append(f"[{location}] 指标 {name} 类型异常：{actual!r}")
                    continue
                if not _values_match(val, actual_f):
                    errors.append(
                        f"[{location}] 数值不一致：{name}={val}（应为 {actual_f}）"
                    )

    # 未包含任何引用 → 未遵守引用规则，视为不可信
    if checked == 0:
        errors.append("报告未包含任何【依据】引用，无法核验结论")

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
        citations_checked=checked,
        hallucinated_metrics=hallucinated,
    )
