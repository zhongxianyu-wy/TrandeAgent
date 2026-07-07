"""T04：validator（校验 + 行号定位）测试。"""
from __future__ import annotations

import pytest

from src.config_manager.validator import (
    ValidationIssue,
    _build_line_map,
    _lookup_line,
    validate_yaml,
)

from tests.config_manager.conftest import VALID_YAML


class TestValidationIssue:
    def test_str_with_line(self):
        issue = ValidationIssue(loc=("field",), msg="bad", type="value_error", line=5)
        s = str(issue)
        assert "field" in s
        assert "bad" in s
        assert "行 5" in s

    def test_str_without_line(self):
        issue = ValidationIssue(loc=(), msg="root err", type="yaml_syntax")
        s = str(issue)
        assert "(root)" in s
        assert "行" not in s


class TestValidateValid:
    def test_valid_yaml_no_issues(self):
        issues = validate_yaml(VALID_YAML)
        assert issues == []

    def test_empty_yaml_uses_defaults(self):
        # 空字符串 -> None -> {} -> 默认值，应通过
        issues = validate_yaml("")
        assert issues == []


class TestValidateSchemaErrors:
    def test_invalid_screener_op(self):
        text = VALID_YAML.replace('op: ">="', 'op: "!="')
        issues = validate_yaml(text)
        assert len(issues) >= 1
        # 应定位到 op 字段
        op_issue = next(i for i in issues if "op" in i.loc)
        assert op_issue.line is not None
        assert op_issue.line >= 1

    def test_invalid_arena_strategy_count(self):
        text = VALID_YAML.replace("strategy_count: 100", "strategy_count: 0")
        issues = validate_yaml(text)
        assert any("strategy_count" in i.loc for i in issues)

    def test_invalid_signal_category(self):
        text = VALID_YAML.replace('category: "technical"', 'category: "bad_cat"')
        issues = validate_yaml(text)
        assert any("category" in i.loc for i in issues)

    def test_line_number_accuracy(self):
        # 构造一个 op 错误在第 7 行的 YAML
        text = (
            "observation_pool:\n"   # 1
            "  - '000001'\n"         # 2
            "screener_rules:\n"      # 3
            "  - name: r1\n"         # 4
            "    field: sharpe\n"    # 5
            "    op: bad_op\n"       # 6
            "    value: 1.0\n"       # 7
        )
        issues = validate_yaml(text)
        assert len(issues) >= 1
        op_issue = next(i for i in issues if "op" in i.loc)
        assert op_issue.line == 6

    def test_top_level_not_mapping(self):
        issues = validate_yaml("- item1\n- item2\n")
        assert len(issues) == 1
        assert issues[0].type == "yaml_type"


class TestValidateYamlSyntax:
    def test_syntax_error_has_line(self):
        text = "observation_pool:\n  - [unclosed\n"
        issues = validate_yaml(text)
        assert len(issues) == 1
        assert issues[0].type == "yaml_syntax"
        assert issues[0].line is not None


class TestLineMapHelpers:
    def test_build_line_map(self):
        import yaml as _yaml

        text = "a:\n  b: 1\nc:\n  - x\n"
        node = _yaml.compose(text)
        line_map = _build_line_map(node)
        assert ("a",) in line_map
        assert ("a", "b") in line_map
        assert ("c",) in line_map

    def test_lookup_line_exact(self):
        line_map = {("a",): 1, ("a", "b"): 2}
        assert _lookup_line(line_map, ("a", "b")) == 2

    def test_lookup_line_prefix_fallback(self):
        line_map = {("a",): 1}
        assert _lookup_line(line_map, ("a", "b", "c")) == 1

    def test_lookup_line_not_found(self):
        assert _lookup_line({}, ("x",)) is None
