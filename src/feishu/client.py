"""FeishuClient 抽象接口（plan §3 / T02）。

下游业务模块（scheduler / fund-analyzer / signal-engine / strategy-arena）
只依赖此抽象接口，隐藏 lark-cli subprocess 调用细节。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.feishu.cards import FeishuCard


class FeishuClient(ABC):
    """飞书 IO 抽象层（单聊卡片推送 + 多维表格读写）。"""

    @abstractmethod
    def init_base(self, schema_dir: Path) -> str:
        """首次创建 Base + 表 + 字段 + 视图。

        Args:
            schema_dir: Base schema YAML 所在目录。

        Returns:
            新建 Base 的访问 URL。
        """

    @abstractmethod
    def send_card(self, card: FeishuCard) -> str:
        """单聊推送交互卡片。

        Args:
            card: 通过 schema 校验的卡片对象。

        Returns:
            飞书 message_id。
        """

    @abstractmethod
    def batch_upsert(self, table_name: str, records: list[dict]) -> list[str]:
        """批量 upsert（按主键去重，存在则更新）。

        Args:
            table_name: 表名（如 "基金池"）。
            records: 记录列表，每条为 {字段名: 值}。

        Returns:
            写入后的 record_id 列表。
        """

    @abstractmethod
    def query_records(self, table_name: str, filter: dict | None = None) -> list[dict]:
        """查询记录。

        Args:
            table_name: 表名。
            filter: 筛选条件（字段 → 值/条件）。

        Returns:
            记录列表，每条为 dict。
        """

    @abstractmethod
    def update_views(self, table_name: str, views: list[dict]) -> None:
        """更新视图（筛选/排序/分组）。

        Args:
            table_name: 表名。
            views: 视图配置列表，每条含 name / filter / sort / group。
        """

    @abstractmethod
    def health_check(self) -> dict:
        """诊断：lark-cli 是否在 PATH、凭证/token 是否就绪、Base 是否存在。

        Returns:
            {"lark_cli": bool, "token": bool, "base": bool, "advice": list[str]}
            任一 False 时 advice 给出修复建议。
        """
