# 技术选型决策（Step 3 法庭对抗式架构选型）

> 本文档是 Step 3 的产出，采用法庭对抗式方法，模拟 5 个 agent 独立深挖 → 法庭辩论 → Lead 综合判决。
> 调研依据：[docs/research.md](./research.md)
> 决策日期：2026-07-06
> 状态：✅ 已确定，作为 Step 4 PRD 的技术输入

---

## 0. 最终决策（TL;DR）

| 层 | 选型 | 复用/自建/fork | 理由 |
|---|---|---|---|
| **编程语言** | Python 3.11+ | 复用 | AkShare/VectorBT/LLM 生态全在 Python |
| **数据层** | AkShare + SQLite/Parquet 本地缓存 | 复用 | 字段全覆盖、零成本 |
| **指标层** | empyrical + quantstats + pandas-ta | 复用 | 业内标准库 |
| **回测层** | VectorBT（参数扫描）+ Backtrader（精细回测） | 复用 | 双引擎分工 |
| **LLM 层** | DeepSeek-V3 主力 + Qwen-Max 备选 | 复用 | 性价比第一、国内直连 |
| **飞书 IO 层** | lark-cli（subprocess 调用） | 复用 | 省开发量、官方维护 |
| **定时调度** | macOS launchd + chinese_calendar | 复用 | 关机不推、节假日过滤 |
| **配置管理** | YAML + Pydantic | 复用 | 策略规则可版本化 |
| **日志监控** | loguru + 本地文件 | 复用 | 简单可靠 |
| **测试** | pytest | 复用 | Python 标准 |
| **业务编排** | 自建 main.py + 模块化 | **自建** | 业务逻辑独一无二 |
| **策略生成器** | LLM + 差异维度矩阵 | **自建** | 项目核心创新点 |
| **策略竞技场** | VectorBT + 自建排名逻辑 | **自建** | 项目核心创新点 |
| **飞书卡片模板** | 自建 JSON 模板 | **自建** | 业务定制 |

**关键判决：** 全部复用开源/官方工具，零 fork。自建部分仅限业务逻辑（策略生成器、竞技场排名、飞书卡片模板）。

---

## 1. Phase 1：5 个 Agent 独立深挖（模拟）

### Agent A：数据采集专家视角

**主张：** AkShare 单源即可，不需要 Tushare。

**证据：**
1. AkShare 字段覆盖度评估：✅ 基本面 / ✅ 净值 / ✅ 经理 / ✅ 持仓 / ✅ 排名 / ⚠️ 现金流（推算）
2. Tushare 高级字段（机构持有、ETF 份额）需 5000-8000 积分，新用户积分不足
3. AkShare 反爬强度低（1 req/s 无压力）
4. 项目用量级（8000 基金 × 日频）AkShare 完全可承受

**架构建议：**
```
DataProvider (抽象接口)
  └── AkShareProvider (实现)
       ├── 本地缓存层 (Parquet/SQLite)
       ├── 限流层 (1 req/s + UA 轮换)
       └── 失败重试 + 降级
```

### Agent B：回测性能专家视角

**主张：** VectorBT 主力 + Backtrader 备选，不要混用主流。

**证据：**
1. 性能：VectorBT 处理 1000 股票 × 10 年 = 8 分钟，Backtrader 需 2 小时（45× 加速）
2. 本项目用量：50-200 策略 × 3-5 年 × 8000 基金 = 大规模参数扫描，**只有向量化能跑**
3. VectorBT 中文文档稀缺但英文官方齐全，社区活跃
4. Backtrader 在精细事件回测（含手续费/滑点/分笔）上不可替代

**架构建议：**
```
BacktestEngine (抽象接口)
  ├── VectorBTEngine (参数扫描，50-200 策略并行)
  └── BacktraderEngine (Top-5 策略精细回测)
```

### Agent C：LLM 与防幻觉专家视角

**主张：** DeepSeek-V3 主力，不上 RAG，靠 prompt + 代码后校验防幻觉。

**证据：**
1. 月度成本：DeepSeek-V3 ≈ ¥2.4，Qwen-Max ≈ ¥62，预算不构成约束
2. 国内可达性：DeepSeek/Qwen 直连，OpenAI/Claude 需中转（合规风险）
3. 中文金融语料：DeepSeek/Qwen 在 SuperCLUE-Fin 位居前列
4. 防幻觉：结构化指标 JSON + 强约束 prompt + 代码侧后校验，三层防御足够
5. RAG 反而引入新幻觉面（基金定期报告本身就有 LLM 误读风险）

**架构建议：**
```
LLMClient (抽象接口，环境变量切换)
  ├── DeepSeekClient (主力)
  └── QwenClient (备选)
      ├── 强约束 prompt 模板（强制引用）
      ├── JSON mode 输出
      └── 后校验（引用指标必须存在于输入）
```

### Agent D：飞书集成专家视角

**主张：** lark-cli 优先，不引入 SDK，Python 用 subprocess 调用。

**证据：**
1. lark-cli 真实存在（npm `@larksuite/cli`、GitHub `larksuite/cli`、本机已装 skills）
2. 能力等价：lark-cli 与官方 SDK 共享同一套 OpenAPI
3. 优势：省去 token 管理/重试/错误码处理代码
4. 劣势：子进程调用有 ~50ms 开销，但日频场景可忽略
5. 个人开发者零成本：免费建飞书团队 + 自建应用，无需企业认证

**架构建议：**
```
FeishuClient (抽象接口)
  └── LarkCLIClient (subprocess 调用 lark-cli)
       ├── IM: im +messages-send (bot 推送卡片)
       └── Base: base +record-batch-create (user 写多维表格)
```

### Agent E：系统工程专家视角

**主张：** macOS launchd 定时 + 本地 SQLite/Parquet + YAML 配置 + loguru 日志。

**证据：**
1. 定时：launchd 原生支持 macOS，开机自动加载，符合"关机不推"约束
2. 节假日过滤：chinese_calendar 库判定 A 股交易日
3. 配置：策略规则必须 YAML 化（呼应 US-5 验收点），Pydantic 校验
4. 日志：loguru 简单可靠，本地文件轮转
5. 测试：pytest 标准，覆盖率目标 > 70%
6. **不引入**：Celery（过度工程）、Redis（无并发需求）、Docker（本地单进程够用）

**架构建议：**
```
Runtime
  ├── launchd plist (定时触发)
  ├── main.py (业务编排)
  ├── config/strategies.yaml (策略配置)
  ├── data/cache/ (本地缓存)
  └── logs/ (日志轮转)
```

---

## 2. Phase 2：法庭辩论（模拟 1 轮）

### 辩论点 1：是否需要 Tushare 作为 AkShare 降级？

- **Agent A（数据）**：建议加 Tushare 备用
- **Agent E（系统）**：反对，增加复杂度，本项目用量级不会触发 AkShare 限流
- **Lead 判决**：**不加**。架构上保留 `DataProvider` 接口，未来需要时可插入。MVP 单源。

### 辩论点 2：lark-cli vs Python SDK（lark-oapi）？

- **Agent D（飞书）**：lark-cli 省 80% 开发量
- **Agent E（系统）**：subprocess 在 macOS launchd 环境下有 PATH 风险
- **Lead 判决**：**lark-cli 优先，但要封装**。`FeishuClient` 接口下默认 lark-cli，未来可平滑切到 `lark-oapi` Python SDK。launchd plist 必须显式指定 PATH。

### 辩论点 3：VectorBT 还是 Backtrader 选一个？

- **Agent B（回测）**：VectorBT 性能 45× 优势在参数扫描场景不可替代
- **Agent A（数据）**：VectorBT 中文资料少，新手学习成本高
- **Lead 判决**：**两个都用**。VectorBT 跑参数扫描（50-200 策略并行），Backtrader 跑 Top-5 精细回测（含手续费/滑点）。学习成本可接受，因为策略竞技场是核心创新。

### 辩论点 4：是否引入 RAG 增强 LLM？

- **Agent C（LLM）**：反对，引入新幻觉面
- **Agent D（飞书）**：建议用基金定期报告做 RAG 增强
- **Lead 判决**：**MVP 不上 RAG**（呼应调研结论）。结构化指标 + 强约束 prompt + 后校验三层防御足够。Roadmap 考虑用基金定期报告做归因叙事增强。

### 辩论点 5：策略生成器用 LLM 还是规则模板？

- **Agent C（LLM）**：LLM 生成有创新性，但同质化风险高（R9）
- **Agent B（回测）**：规则模板更可控，但缺创新
- **Lead 判决**：**混合方案**。规则模板（15 个策略原型）+ LLM 在差异维度矩阵（5 维 2048 组合）约束下做参数变体生成。LLM 不得凭空发明策略原型，只能在现成原型上做参数空间探索。

---

## 3. Phase 3：Lead 综合判决

### 3.1 技术栈定案

```ascii
┌─────────────────────────────────────────────────────────────┐
│  TrandeAgent 系统架构                                         │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  定时层 (macOS launchd, 16:00 触发)                     │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  业务编排层 (main.py)                                    │ │
│  └─────┬───────────┬───────────┬───────────┬───────────────┘ │
│        ▼           ▼           ▼           ▼                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────┐   │
│  │ DataProv │ │ Indicator│ │ Backtest │ │  LLM Client  │   │
│  │ AkShare  │ │ empyrical│ │ VectorBT │ │  DeepSeek-V3 │   │
│  │ +Cache   │ │ quantstats│ │ Backtrad │ │  +后校验     │   │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬────────┘   │
│       │            │            │             │              │
│       ▼            ▼            ▼             ▼              │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  业务模块层                                              │ │
│  │  ├── FundScreener (基金池筛选)                          │ │
│  │  ├── FundAnalyzer (单基金深度分析)                      │ │
│  │  ├── SignalEngine (择时信号)                            │ │
│  │  ├── StrategyArena (策略模拟竞技场)                     │ │
│  │  │   ├── StrategyGenerator (LLM 生成 50-200 策略)       │ │
│  │  │   ├── BacktestRunner (历史回测)                      │ │
│  │  │   └── ForwardSimulator (纸上模拟)                    │ │
│  │  └── ReportRenderer (报告渲染)                          │ │
│  └────────────────────────┬────────────────────────────────┘ │
│                           ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  飞书 IO 层 (FeishuClient → lark-cli subprocess)        │ │
│  │  ├── IM: 单聊推送卡片                                   │ │
│  │  └── Base: 多维表格读写                                 │ │
│  └─────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 目录结构定案

```
TrandeAgent/
├── docs/                    # 文档（context.md, research.md, prd.md, adr.md）
├── specs/                   # Spec-Kit 输出（Step 5 产出）
├── src/
│   ├── data/                # 数据层
│   │   ├── provider.py      # DataProvider 抽象
│   │   ├── akshare_provider.py
│   │   └── cache.py         # SQLite/Parquet 缓存
│   ├── indicators/          # 指标层
│   │   ├── fundamentals.py  # L1 基本面
│   │   ├── performance.py   # L2 业绩
│   │   ├── style.py         # L3 风格
│   │   └── cashflow.py      # L4 现金流
│   ├── backtest/            # 回测层
│   │   ├── engine.py        # 抽象接口
│   │   ├── vectorbt_engine.py
│   │   └── backtrader_engine.py
│   ├── llm/                 # LLM 层
│   │   ├── client.py        # LLMClient 抽象
│   │   ├── deepseek_client.py
│   │   ├── prompts.py       # 强约束 prompt 模板
│   │   └── validator.py     # 后校验
│   ├── arena/               # 策略竞技场（核心）
│   │   ├── generator.py     # 策略生成器
│   │   ├── strategies/      # 15 个策略原型
│   │   ├── ranking.py       # 领域 Top-5 排名
│   │   └── mind_models/     # 8 位大师心智模型
│   ├── feishu/              # 飞书 IO
│   │   ├── client.py        # FeishuClient
│   │   ├── cards.py         # 卡片模板
│   │   └── base_schema.py   # 多维表格 schema
│   ├── modules/             # 业务模块
│   │   ├── screener.py      # 基金池筛选
│   │   ├── analyzer.py      # 单基金分析
│   │   ├── signal.py        # 择时信号
│   │   └── reporter.py      # 报告渲染
│   ├── config.py            # Pydantic 配置加载
│   └── main.py              # 业务编排入口
├── config/
│   ├── strategies.yaml      # 策略规则配置
│   ├── mind_models.yaml     # 大师心智模型参数
│   └── feishu_base_schema.yaml
├── tests/                   # pytest 测试
├── scripts/
│   └── install_launchd.sh   # launchd 安装脚本
├── .gitignore
├── pyproject.toml           # Poetry/uv 项目配置
└── README.md
```

### 3.3 关键技术决策记录（ADR）

#### ADR-001：数据源选 AkShare 单源
- **状态：** 已接受
- **背景：** 需要全市场公募基金日频数据，含经理/持仓/份额
- **决策：** AkShare 单源 + 本地缓存
- **替代方案：** Tushare（高级字段需积分，本项目用量级用不到）
- **后果：** 正向：零成本、字段全；负向：上游改版风险（用单元测试+多接口降级应对）

#### ADR-002：LLM 选 DeepSeek-V3
- **状态：** 已接受
- **背景：** 需要把结构化指标翻译成中文报告 + AI 辅助决策
- **决策：** DeepSeek-V3 主力 + Qwen-Max 备选，抽象 LLMClient 接口
- **替代方案：** OpenAI/Claude（国内需中转，合规风险）
- **后果：** 正向：国内直连、性价比第一；负向：质量略低于 GPT-4o（用 Qwen-Max 高质量档弥补）

#### ADR-003：飞书集成用 lark-cli
- **状态：** 已接受
- **背景：** 需要单聊推送卡片 + 多维表格读写
- **决策：** lark-cli subprocess 调用，封装 FeishuClient 接口
- **替代方案：** lark-oapi Python SDK（增加 token 管理代码量）
- **后果：** 正向：省 80% 开发量；负向：subprocess PATH 风险（launchd plist 显式指定 PATH）

#### ADR-004：回测双引擎 VectorBT + Backtrader
- **状态：** 已接受
- **背景：** 50-200 策略 × 3-5 年 × 8000 基金的参数扫描
- **决策：** VectorBT 跑参数扫描，Backtrader 跑 Top-5 精细回测
- **替代方案：** 单一框架（性能或精度不可兼得）
- **后果：** 正向：性能 + 精度兼得；负向：学习两套框架（可接受）

#### ADR-005：不上 RAG
- **状态：** 已接受
- **背景：** LLM 防幻觉需求
- **决策：** MVP 用结构化指标 + 强约束 prompt + 代码后校验三层防御
- **替代方案：** RAG（引入基金定期报告）
- **后果：** 正向：架构简单、无新幻觉面；负向：归因叙事不如 RAG 丰富（Roadmap 再上）

#### ADR-006：策略生成混合方案
- **状态：** 已接受
- **背景：** 50-200 差异化策略生成，避免同质化
- **决策：** 规则模板（15 原型）+ LLM 在差异维度矩阵（5 维 2048 组合）约束下生成
- **替代方案：** 纯 LLM 生成（同质化高）/ 纯规则（无创新）
- **后果：** 正向：可控 + 创新；负向：LLM 不得凭空发明原型（prompt 强约束）

#### ADR-007：定时调度用 macOS launchd
- **状态：** 已接受
- **背景：** 每日 16:00 推送，关机不推，节假日不发
- **决策：** launchd `StartCalendarInterval` + chinese_calendar 交易日过滤
- **替代方案：** APScheduler 常驻进程（违背"关机不推"）
- **后果：** 正向：原生、零依赖；负向：迁云时需替换（保留迁移空间）

---

## 4. 风险与缓解

| 风险 | 缓解 |
|---|---|
| AkShare 接口 break | 单元测试覆盖关键接口 + 多接口降级 |
| lark-cli subprocess PATH 问题 | launchd plist 显式 PATH + 启动诊断脚本 |
| LLM 幻觉 | 三层防御（prompt + JSON mode + 后校验） |
| VectorBT 学习曲线高 | 先用 Backtrader 跑通 MVP，VectorBT 渐进迁移 |
| 50-200 策略同质化 | 差异维度矩阵强制约束 + 去重检查 |
| 回测过拟合 | 双轨并行（回测+纸上模拟），纸上满 30 交易日才能进 Top-5 |

---

## 5. 与 context.md 的映射

本决策完全基于 [docs/context.md](./context.md) 的需求边界：
- 数据源决策 ← context.md 4.1 数据源行
- LLM 决策 ← context.md 4.1 策略深度行 + AI 成本约束
- 飞书决策 ← context.md 4.1 飞书接入形态行
- 策略竞技场 ← context.md US-6 + v0.2 新增行
- 定时调度 ← context.md 4.1 推送频率 + 运行环境行

所有 ADR 可追溯到 context.md 的具体决策点，无凭空设计。
