"""飞书交互卡片 Pydantic schema（plan §2.2 / FR-1 / T03）。

卡片 JSON 必须通过 schema 校验后才能推送，非法结构抛 ValidationError。
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class CardElement(BaseModel):
    """卡片内容元素。

    支持 tag: markdown / action / column_set / hr。
    元素自身的附加字段（content / actions / columns 等）透传给 lark-cli。
    """

    tag: Literal["markdown", "action", "column_set", "hr"]
    model_config = ConfigDict(extra="allow")


class CardAction(BaseModel):
    """卡片按钮动作（可出现在 elements 列表或 action 元素的 actions 中）。"""

    tag: Literal["button"] = "button"
    text: dict
    type: Literal["primary", "default"] = "primary"
    open_url: str | None = None
    model_config = ConfigDict(extra="allow")


class FeishuCard(BaseModel):
    """飞书交互卡片顶层模型。

    header: {"template": "blue", "title": {"content": "..."}}
    elements: 元素列表，每个为 CardElement 或 CardAction。
    """

    header: dict
    elements: list[Union[CardElement, CardAction]] = Field(default_factory=list)


class BaseRecord(BaseModel):
    """多维表格单条记录（字段名 → 值），用于写入前校验。"""

    fields: dict = Field(default_factory=dict)
    record_id: str | None = None
    model_config = ConfigDict(extra="allow")
