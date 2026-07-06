# Feature #9 — config-manager 实施计划

> 含 5 要素（精简）

---

## 1. 技术选型
- `pydantic` ≥2.0 schema 校验
- `pyyaml` ≥6.0 加载
- `gitpython` ≥3.1 版本管理
- `deepdiff` ≥6.0 配置 diff

---

## 2. 数据模型

```python
class AppConfig(BaseModel):
    observation_pool: list[str]              # 观察池
    screener_rules: list[Rule]               # 来自 #5
    signal_rules: list[SignalRule]           # 来自 #7
    arena: ArenaConfig                       # 来自 #8

class ChangeImpact(BaseModel):
    change_type: Literal["screener", "signal", "arena"]
    added: list[str]
    removed: list[str]
    affected_funds: list[str]
    requires_backtest_rerun: bool
```

---

## 3. 接口契约
```python
class ConfigManager(ABC):
    @abstractmethod
    def load(self, path: Path) -> AppConfig: ...
    @abstractmethod
    def validate(self, yaml_text: str) -> list[ValidationError]: ...
    @abstractmethod
    def analyze_impact(self, old: AppConfig, new: AppConfig) -> ChangeImpact: ...
    @abstractmethod
    def save_with_commit(self, config: AppConfig, msg: str) -> None: ...
    @abstractmethod
    def rollback(self, commit_hash: str) -> AppConfig: ...
```

---

## 4. 依赖
- 上游：#5, #7
- 下游：所有模块

---

## 5. 测试策略
- 单元：每类规则校验、diff 计算
- 集成：save → analyze_impact → rollback
- 性能：校验 < 1s

覆盖率 > 85%。

---

## 6. 关键决策
- 影响范围检测同步（< 5s 可接受）
- 配置变更触发 git commit（用户可关闭）

---

## 7. 目录结构
```
src/config_manager/
├── __init__.py
├── schema.py              # Pydantic 模型
├── loader.py
├── impact.py              # 影响范围
├── version.py             # git 版本管理
└── __main__.py            # CLI
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
