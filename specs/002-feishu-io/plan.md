# Feature #2 — feishu-io 实施计划

> **Spec-Kit plan 产出** | 含 5 要素

---

## 1. 技术选型

| 库 / 工具 | 版本 | 用途 | 理由 |
|---|---|---|---|
| `lark-cli`（npm `@larksuite/cli`） | latest | 飞书 IO 命令行 | 官方维护，省 80% 开发量（见 research.md §2.6） |
| Python `subprocess` | 内置 | 调用 lark-cli | 零依赖 |
| `tenacity` | ≥8.0 | 重试 | 与 #1 一致 |
| `pydantic` | ≥2.0 | 卡片/记录 schema 校验 | |
| `pyyaml` | ≥6.0 | Base schema 配置 | 可版本化 |
| `shellingham` | ≥1.5 | 检测 shell（诊断 PATH） | launchd 兼容 |

**不引入：** `lark-oapi` Python SDK（subprocess 已够，未来需平滑切换时再引入）。

---

## 2. 数据模型

### 2.1 配置文件 `config/feishu.yaml`
```yaml
app_id: ${FEISHU_APP_ID}      # 环境变量
app_secret: ${FEISHU_APP_SECRET}
user_open_id: "ou_xxxxxxxxxxxxxxxx"  # 推送目标
base_token: ""                  # 首次 init 后自动填充
base_url: ""                    # 首次 init 后自动填充

tables:
  - name: "基金池"
    table_id: ""
    fields_file: "config/feishu_base_fund_pool.yaml"
  - name: "信号"
    table_id: ""
    fields_file: "config/feishu_base_signals.yaml"
  - name: "策略竞技场"
    table_id: ""
    fields_file: "config/feishu_base_arena.yaml"
  - name: "复盘"
    table_id: ""
    fields_file: "config/feishu_base_review.yaml"

rate_limit:
  msg_qps: 5
  base_batch_size: 200
  base_batch_interval_sec: 0.5

retry:
  max_attempts: 3
  backoff: [1, 2, 4]
```

### 2.2 卡片 JSON Schema（Pydantic）
```python
class CardElement(BaseModel):
    tag: Literal["markdown", "action", "column_set", "hr"]

class CardAction(BaseModel):
    tag: Literal["button"] = "button"
    text: dict
    type: Literal["primary", "default"] = "primary"
    open_url: str | None = None

class FeishuCard(BaseModel):
    header: dict  # {template, title}
    elements: list[CardElement | CardAction]
```

---

## 3. 接口契约

```python
from abc import ABC, abstractmethod
from pathlib import Path

class FeishuClient(ABC):
    """飞书 IO 抽象层。下游只依赖此接口。"""

    @abstractmethod
    def init_base(self, schema_dir: Path) -> str:
        """首次创建 Base + 4 表 + 视图。返回 base_url。"""

    @abstractmethod
    def send_card(self, card: FeishuCard) -> str:
        """单聊推送卡片。返回 message_id。"""

    @abstractmethod
    def batch_upsert(self, table_name: str, records: list[dict]) -> list[str]:
        """批量 upsert。返回 record_ids。"""

    @abstractmethod
    def query_records(self, table_name: str, filter: dict | None = None) -> list[dict]:
        """查询记录。"""

    @abstractmethod
    def update_views(self, table_name: str, views: list[dict]) -> None:
        """更新视图（筛选/排序/分组）。"""

    @abstractmethod
    def health_check(self) -> dict:
        """诊断：lark-cli 是否在 PATH、token 是否有效、Base 是否存在。"""
```

### `LarkCLIClient` 实现要点
- 内部维护 `_run(cmd: list[str]) -> CompletedProcess`，封装 subprocess
- subprocess 调用时显式传 `env={"PATH": <explicit_path>, **os.environ}`（launchd 兼容）
- 每个 lark-cli 调用走 `tenacity.retry`（3 次，指数退避）
- 错误码识别：1254104（批量超限降批）、91403（无权限告警）、1254064（日期格式校验）

---

## 4. 依赖列表

### 上游
- npm + lark-cli 全局安装（`npm install -g @larksuite/cli`）
- 飞书自建应用（appId/appSecret）
- 用户 OAuth 授权（`lark-cli auth login --scope base:app:read/write im:message:send_as_bot`）

### 模块内
- 无

### 下游
- #3 scheduler（推送失败时告警）
- #6 fund-analyzer（推送分析报告卡片）
- #7 signal-engine（推送信号卡片）
- #8 strategy-arena（写竞技场表）

---

## 5. 测试策略

| 层级 | 工具 | 覆盖点 |
|---|---|---|
| 单元 | pytest + mock subprocess | 各方法 happy path |
| 集成 | mock lark-cli stdout | init_base / batch_upsert 全流程 |
| 配置校验 | pydantic | schema 错误抛异常 |
| 错误码 | mock stderr | 1254104 降批、91403 告警 |
| 烟雾 | 手动 | 真实飞书应用 1 条推送 |

覆盖率目标 > 80%。

---

## 6. 关键决策（小 ADR）

### 为什么用 subprocess + lark-cli 而非 lark-oapi SDK
- 省去 token 管理/刷新/错误码处理代码
- 调用形态：`subprocess.run(["lark-cli", "im", "+messages-send", ...])`
- 未来需要时，`FeishuClient` 抽象层下可平滑插入 `LarkSDKClient`

### 为什么 Base schema 用 YAML 而非代码定义
- 用户可读可改（如新增字段）
- 版本管理（Git diff 看历史变更）
- init_base 时按 YAML 创建

---

## 7. 目录结构
```
src/feishu/
├── __init__.py
├── client.py            # FeishuClient 抽象
├── lark_cli_client.py   # LarkCLIClient 实现
├── cards.py             # 卡片模板（Pydantic schema）
├── base_schema.py       # Base schema 加载与创建
├── error_codes.py       # 错误码映射
└── __main__.py          # CLI: feishu init / health / test-push

config/
├── feishu.yaml
└── feishu_base_*.yaml   # 4 张表的 schema

tests/feishu/
├── test_client.py
├── test_cards.py
├── test_base_schema.py
└── fixtures/
    └── lark_cli_mock.json
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
