"""T07: Base schema 加载测试。"""
from __future__ import annotations

from pathlib import Path

import pytest

from src.feishu.base_schema import load_schema_dir, load_table_schema
from src.feishu.error_codes import SchemaError

REAL_SCHEMA_DIR = Path(__file__).resolve().parent.parent.parent / "config" / "feishu_base_schemas"


class TestBaseSchema:
    def test_load_fund_pool(self):
        schema = load_table_schema(REAL_SCHEMA_DIR / "fund_pool.yaml")
        assert schema.table_name == "基金池"
        codes = [f.name for f in schema.fields]
        assert "基金代码" in codes
        pk = schema.primary_key_field
        assert pk is not None and pk.name == "基金代码"
        assert pk.primary_key is True
        # 视图定义存在
        view_names = [v.name for v in schema.views]
        assert "今日候选" in view_names

    def test_load_signals(self):
        schema = load_table_schema(REAL_SCHEMA_DIR / "signals.yaml")
        assert schema.table_name == "信号"
        assert schema.primary_key_field.name == "日期"

    def test_load_all_four(self):
        schemas = load_schema_dir(REAL_SCHEMA_DIR)
        names = [s.table_name for s in schemas]
        # 文件按文件名排序加载，此处只校验 4 张表齐全
        assert set(names) == {"基金池", "信号", "策略竞技场", "复盘"}
        assert len(names) == 4

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(SchemaError):
            load_table_schema(tmp_path / "nope.yaml")

    def test_missing_fields_raises(self, tmp_path):
        p = tmp_path / "bad.yaml"
        p.write_text("table_name: 'x'\n", encoding="utf-8")
        with pytest.raises(SchemaError):
            load_table_schema(p)

    def test_missing_dir_raises(self, tmp_path):
        with pytest.raises(SchemaError):
            load_schema_dir(tmp_path / "nodir")

    def test_empty_dir_raises(self, tmp_path):
        with pytest.raises(SchemaError):
            load_schema_dir(tmp_path)

    def test_field_property_parsed(self):
        schema = load_table_schema(REAL_SCHEMA_DIR / "fund_pool.yaml")
        type_field = next(f for f in schema.fields if f.name == "类型")
        assert type_field.type == "single_select"
        assert "options" in type_field.property

    def test_view_filter_sort(self):
        schema = load_table_schema(REAL_SCHEMA_DIR / "fund_pool.yaml")
        today = next(v for v in schema.views if v.name == "今日候选")
        assert today.filter == {"添加日期": "today"}
        assert today.sort == {"评级": "desc"}
