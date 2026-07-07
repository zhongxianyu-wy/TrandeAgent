"""T03: 卡片 Pydantic schema 单元测试。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.feishu.cards import BaseRecord, CardAction, CardElement, FeishuCard


class TestCardSchema:
    def test_valid_card_with_markdown(self):
        card = FeishuCard(
            header={"template": "blue", "title": {"content": "每日报告"}},
            elements=[CardElement(tag="markdown", content="**组合表现**: +0.85%")],
        )
        dumped = card.model_dump()
        assert dumped["header"]["template"] == "blue"
        assert dumped["elements"][0]["tag"] == "markdown"
        # 附加字段 content 透传
        assert dumped["elements"][0]["content"] == "**组合表现**: +0.85%"

    def test_valid_card_with_action_and_button(self):
        card = FeishuCard(
            header={"template": "green"},
            elements=[
                CardElement(
                    tag="action",
                    actions=[
                        CardAction(
                            text={"content": "查看详情"},
                            type="primary",
                            open_url="https://feishu.cn/base/xxx",
                        ).model_dump()
                    ],
                )
            ],
        )
        assert card.elements[0].tag == "action"

    def test_button_action_defaults(self):
        btn = CardAction(text={"content": "ok"})
        assert btn.tag == "button"
        assert btn.type == "primary"
        assert btn.open_url is None

    def test_button_action_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            CardAction(text={"content": "x"}, type="danger")  # type: ignore[arg-type]

    def test_standalone_button_in_elements(self):
        card = FeishuCard(
            header={"template": "red"},
            elements=[CardAction(text={"content": "确认"}, type="default")],
        )
        assert isinstance(card.elements[0], CardAction)

    def test_invalid_element_tag_raises(self):
        with pytest.raises(ValidationError):
            FeishuCard(
                header={"template": "blue"},
                elements=[{"tag": "unknown_tag"}],  # type: ignore[list-item]
            )

    def test_missing_header_raises(self):
        with pytest.raises(ValidationError):
            FeishuCard(elements=[CardElement(tag="hr")])  # type: ignore[call-arg]

    def test_hr_element(self):
        card = FeishuCard(header={"template": "blue"}, elements=[CardElement(tag="hr")])
        assert card.elements[0].tag == "hr"

    def test_baserecord(self):
        rec = BaseRecord(fields={"基金代码": "000001"}, record_id="rec123")
        assert rec.record_id == "rec123"
        assert rec.fields["基金代码"] == "000001"

    def test_card_from_dict_roundtrip(self):
        raw = {
            "header": {"template": "blue", "title": {"content": "x"}},
            "elements": [
                {"tag": "markdown", "content": "hi"},
                {"tag": "button", "text": {"content": "go"}, "open_url": "u"},
            ],
        }
        card = FeishuCard.model_validate(raw)
        assert len(card.elements) == 2
