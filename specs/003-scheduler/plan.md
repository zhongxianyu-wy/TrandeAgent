# Feature #3 — scheduler 实施计划

> 含 5 要素

---

## 1. 技术选型

| 库 | 版本 | 用途 |
|---|---|---|
| `chinese_calendar` | ≥1.9 | A 股交易日判定 |
| `pyyaml` | ≥6.0 | 配置 |
| Python 内置 `subprocess` | - | launchctl 命令 |
| Python 内置 `json` | - | 状态文件 |

**不引入：** APScheduler（违背"关机不推"约束）、Celery（过度工程）。

---

## 2. 数据模型

### `config/scheduler.yaml`
```yaml
trigger_time: "16:00"            # HH:MM
timezone: "Asia/Shanghai"
backfill_max_days: 5             # 漏推送补发上限
holidays_source: "chinese_calendar"  # 备选: custom
```

### `data/state/last_run.json`
```json
{
  "last_run_date": "2026-07-04",
  "last_run_at": "2026-07-04T16:00:00+08:00",
  "last_status": "success",
  "last_duration_sec": 1820
}
```

### `data/state/run_history.jsonl`
```json
{"run_at": "2026-07-04T16:00:00+08:00", "status": "success", "duration_sec": 1820, "fund_count": 7823, "mode": "daily"}
```

---

## 3. 接口契约

```python
from abc import ABC, abstractmethod
from datetime import date

class Scheduler(ABC):
    @abstractmethod
    def should_run_today(self, today: date) -> bool:
        """判定今日是否应运行（交易日过滤）。"""

    @abstractmethod
    def detect_missed_runs(self) -> list[date]:
        """检测漏推送的交易日列表。"""

    @abstractmethod
    def backfill(self, dates: list[date]) -> None:
        """补发指定日期的报告。"""

    @abstractmethod
    def record_run(self, status: str, duration_sec: int, mode: str) -> None:
        """记录本次运行到历史。"""

class LaunchdScheduler(Scheduler):
    """macOS launchd 实现。"""
    def install(self) -> None: ...
    def uninstall(self) -> None: ...
    def is_installed(self) -> bool: ...
```

### launchd plist 模板
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.trandeagent.daily</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/env</string>
        <string>PATH=/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <string>python</string>
        <string>-m</string>
        <string>src.main</string>
        <string>daily</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>16</integer>
        <key>Minute</key><integer>0</integer>
    </dict>
    <key>StandardOutPath</key><string>/Volumes/exp/agentproject/TrandeAgent/logs/launchd.out.log</string>
    <key>StandardErrorPath</key><string>/Volumes/exp/agentproject/TrandeAgent/logs/launchd.err.log</string>
    <key>WorkingDirectory</key><string>/Volumes/exp/agentproject/TrandeAgent</string>
</dict>
</plist>
```

---

## 4. 依赖列表
- 上游：macOS launchd（系统原生）、`chinese_calendar`（每年更新节假日）
- 模块内：无
- 下游：main.py（编排所有业务模块）

---

## 5. 测试策略

| 测试 | 覆盖点 |
|---|---|
| `test_should_run_today` | 工作日 True、周末 False、节假日（mock chinese_calendar）False |
| `test_detect_missed_runs` | 距上次 0/1/3/7 交易日的检测 |
| `test_backfill_limit` | 超 5 天不补 |
| `test_install_plist` | plist 文件生成 + 字段校验 |
| `test_record_run` | jsonl 追加 |

覆盖率 > 85%。

---

## 6. 关键决策

### 为什么 launchd 不用 APScheduler
- launchd 关机不运行，开机后由 launchd 触发补发逻辑
- APScheduler 需常驻进程，违背"关机不推"

### 为什么补发上限 5 天
- 更早的报告意义不大（数据已陈旧）
- 上限避免一次性补发过多卡片刷屏

---

## 7. 目录结构
```
src/scheduler/
├── __init__.py
├── scheduler.py            # Scheduler 抽象
├── launchd_scheduler.py    # macOS 实现
├── holiday.py              # 交易日判定
├── state.py                # last_run / run_history
└── __main__.py             # CLI: install/uninstall/status/run

scripts/
└── install_launchd.sh      # 一键安装脚本

tests/scheduler/
├── test_holiday.py
├── test_state.py
└── test_backfill.py
```

---

## 变更记录
| 版本 | 日期 | 变更 | 作者 |
|---|---|---|---|
| v0.1 | 2026-07-06 | plan 初稿 | 小瑶 |
