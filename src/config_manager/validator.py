"""配置校验 + 行号定位（T04）。

使用 Pydantic 校验 YAML schema，并通过 PyYAML 的 compose 解析节点树，
把每条错误定位到 YAML 源码行号。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml
from pydantic import ValidationError

from src.config_manager.schema import AppConfig


@dataclass
class ValidationIssue:
    """单条校验问题。

    Attributes:
        loc: 错误定位路径（字段名 / 列表索引）。
        msg: 错误信息。
        type: 错误类型（pydantic error type 或 ``yaml_syntax``）。
        line: YAML 源码行号（1-based），无法定位时为 None。
    """

    loc: tuple[str | int, ...]
    msg: str
    type: str
    line: int | None = None

    def __str__(self) -> str:
        loc_str = ".".join(str(x) for x in self.loc) if self.loc else "(root)"
        line_str = f" (行 {self.line})" if self.line else ""
        return f"[{self.type}] {loc_str}: {self.msg}{line_str}"


def _build_line_map(node: Any, prefix: tuple = ()) -> dict[tuple, int]:
    """递归遍历 YAML node 树，构建 (loc_tuple) -> 行号 映射。

    start_mark.line 是 0-based，统一转成 1-based。
    """
    mapping: dict[tuple, int] = {}
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            key = key_node.value
            current_loc = prefix + (key,)
            mapping[current_loc] = key_node.start_mark.line + 1
            mapping.update(_build_line_map(value_node, current_loc))
    elif isinstance(node, yaml.SequenceNode):
        for i, item_node in enumerate(node.value):
            current_loc = prefix + (i,)
            mapping[current_loc] = item_node.start_mark.line + 1
            mapping.update(_build_line_map(item_node, current_loc))
    return mapping


def _lookup_line(
    line_map: dict[tuple, int], loc: tuple[str | int, ...]
) -> int | None:
    """根据 loc 查找行号，找不到则逐步缩短前缀。"""
    if loc in line_map:
        return line_map[loc]
    for i in range(len(loc) - 1, 0, -1):
        if loc[:i] in line_map:
            return line_map[loc[:i]]
    return None


def validate_yaml(yaml_text: str) -> list[ValidationIssue]:
    """校验 YAML 文本，返回问题列表（空列表表示通过）。

    先做 YAML 语法解析（捕获行号），再用 Pydantic 做 schema 校验。
    """
    # 1. YAML 语法校验 + compose 节点树
    try:
        composed = yaml.compose(yaml_text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = (mark.line + 1) if mark is not None and mark.line is not None else None
        return [
            ValidationIssue(
                loc=(),
                msg=f"YAML 语法错误: {e.problem if hasattr(e, 'problem') else e}",
                type="yaml_syntax",
                line=line,
            )
        ]

    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as e:  # 极少数 compose 通过但 safe_load 失败
        mark = getattr(e, "problem_mark", None)
        line = (mark.line + 1) if mark is not None and mark.line is not None else None
        return [
            ValidationIssue(
                loc=(),
                msg=f"YAML 解析错误: {e}",
                type="yaml_syntax",
                line=line,
            )
        ]

    if data is None:
        data = {}

    if not isinstance(data, dict):
        return [
            ValidationIssue(
                loc=(),
                msg=f"顶层必须是映射（mapping），实际为 {type(data).__name__}",
                type="yaml_type",
            )
        ]

    line_map = _build_line_map(composed) if composed else {}

    # 2. Pydantic schema 校验
    try:
        AppConfig.model_validate(data)
        return []
    except ValidationError as e:
        issues: list[ValidationIssue] = []
        for err in e.errors():
            loc = tuple(err["loc"])
            line = _lookup_line(line_map, loc)
            issues.append(
                ValidationIssue(
                    loc=loc,
                    msg=err["msg"],
                    type=err["type"],
                    line=line,
                )
            )
        return issues
