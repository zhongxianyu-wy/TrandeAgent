# Feature #6 — fund-analyzer 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 | 版本 | 用途 |
|---|---|---|
| `openai` SDK | ≥1.0 | 调用 DeepSeek（OpenAI 兼容） |
| `pydantic` | ≥2.0 | 报告 schema |
| `jinja2` | ≥3.0 | 报告/卡片模板 |
| `tiktoken` | ≥0.5 | token 计数 |

复用 #2 feishu-io 推送。

---

## 2. 数据模型

```python
class ReportSection(BaseModel):
    title: str
    content: str  # 含【依据：...】引用

class FundReport(BaseModel):
    fund_code: str
    one_liner: str               # 一句话结论
    label: Literal["建议", "中性", "回避"]
    sections: list[ReportSection]  # 7 章节
    recommendation_pool: bool      # 是否建议进观察池
    citations: list[dict]          # 引用列表（指标名+数值）

class LLMClient(ABC):
    @abstractmethod
    def analyze_fund(self, metrics: dict) -> dict: ...

class DeepSeekClient(LLMClient):
    """OpenAI 兼容协议调 DeepSeek-V3。"""
```

---

## 3. 接口契约

```python
class FundAnalyzer(ABC):
    @abstractmethod
    def analyze(self, fund_code: str) -> FundReport: ...
    @abstractmethod
    def validate_citations(self, report: FundReport, metrics: dict) -> bool: ...
    @abstractmethod
    def render_card(self, report: FundReport) -> dict: ...
```

---

## 4. 依赖
- 上游：#1, #4, #2
- 下游：无

---

## 5. 测试策略
- 单元：prompt 模板渲染、citation 校验、标签判断
- 集成：mock LLM 返回，跑完 analyze → validate → render
- 防幻觉：构造"LLM 编造指标"用例，验证后校验拦截
- 性能：单基金 ≤ 30s

覆盖率 > 85%（核心在防幻觉）。

---

## 6. 关键决策
- 后校验失败：重试 1 次 → 仍失败则降级到规则评级（用 #4 rating）
- 报告附"原文指标 JSON"折叠区（可读 + 可信）

---

## 7. 目录结构
```
src/analyzer/
├── __init__.py
├── analyzer.py             # FundAnalyzer 抽象
├── llm/
│   ├── client.py           # LLMClient 抽象
│   ├── deepseek_client.py
│   ├── qwen_client.py      # 备选
│   └── prompts.py          # 强约束 prompt 模板
├── validator.py            # 后校验
├── renderer.py             # 渲染卡片/Markdown
└── __main__.py
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
