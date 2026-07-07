"""Base schema YAML 加载（plan §2 / T07 / T08）。

每张表一个 YAML：table_name / fields[] / views[]。
init_base 时按 schema 创建表 + 字段 + 视图。
"""
from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from src.feishu.error_codes import SchemaError


class FieldDef(BaseModel):
    """字段定义。"""

    name: str
    type: str  # text / number / date / single_select / checkbox / formula ...
    primary_key: bool = False
    property: dict = Field(default_factory=dict)
    description: str = ""


class ViewDef(BaseModel):
    """视图定义（筛选/排序/分组）。"""

    name: str
    filter: dict = Field(default_factory=dict)
    sort: dict = Field(default_factory=dict)
    group: dict = Field(default_factory=dict)


class TableSchema(BaseModel):
    """单张表的完整 schema。"""

    table_name: str
    fields: list[FieldDef]
    views: list[ViewDef] = Field(default_factory=list)

    @property
    def primary_key_field(self) -> FieldDef | None:
        for f in self.fields:
            if f.primary_key:
                return f
        return None


def load_table_schema(path: str | Path) -> TableSchema:
    """加载单张表的 schema YAML。"""
    p = Path(path)
    if not p.is_file():
        raise SchemaError(f"schema 文件不存在：{p}")
    with open(p, encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not raw.get("fields"):
        raise SchemaError(f"schema {p} 缺少 fields 定义")
    try:
        return TableSchema(**raw)
    except Exception as e:  # noqa: BLE001
        raise SchemaError(f"schema {p} 解析失败：{e}") from e


def load_schema_dir(schema_dir: str | Path) -> list[TableSchema]:
    """加载目录下所有 *.yaml schema，按文件名排序。"""
    d = Path(schema_dir)
    if not d.is_dir():
        raise SchemaError(f"schema 目录不存在：{d}")
    schemas: list[TableSchema] = []
    for p in sorted(d.glob("*.yaml")):
        schemas.append(load_table_schema(p))
    if not schemas:
        raise SchemaError(f"schema 目录 {d} 下无 *.yaml 文件")
    return schemas
