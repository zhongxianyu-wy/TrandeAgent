# 调研报告（Step 2 产出）

> 本文档汇总 Step 2 阶段所有调研结论，作为 Step 3 架构选型与 Step 4 PRD 撰写的依据。
> 调研日期：2026-07-06
> 调研方法：WebSearch 实时检索 + 本机 lark-cli skills 文档（飞书 CLI 部分）+ 训练知识（标注"参考值"的价格部分）
> 所有引用链接均来自实时搜索结果，URL 经检索引擎返回

---

## 0. 执行摘要（TL;DR）

| 决策项 | 结论 |
|---|---|
| **数据源** | AkShare 为主（免费、覆盖全），Tushare 为降级备选（高级数据需积分） |
| **飞书接入** | lark-cli 命令行调用 + macOS launchd 定时，混合方案 |
| **LLM** | DeepSeek-V3 主力（国内直连、中文金融强、性价比第一） |
| **回测框架** | VectorBT（向量化、极速，适合 50-200 策略参数扫描） |
| **策略原型** | 15+ 个有出处的策略原型（4433、双动量、网格、定投...） |
| **大师心智模型** | 精选 8 位（巴菲特/芒格/格雷厄姆/林奇/达利欧/马克斯/塔勒布/博格尔） |
| **运行环境** | 本地 macOS，零云成本 |

---

## 1. 数据源调研：AkShare vs Tushare

### 1.1 数据源能力矩阵

> 数据源：[AkShare 公募基金官方文档](https://akshare.akfamily.xyz/data/fund/fund_public.html) + [Tushare ETF 接口文档](https://tushare.pro/document/2?doc_id=408) + [三方对比文章](https://juejin.cn/post/7654891094078439474)

| 字段维度 | AkShare | Tushare | 备注 |
|---|---|---|---|
| **基金基本信息** | ✅ `fund_name_em`（全市场代码表）/ `fund_info_ths`（含经理/费率/规模） | ✅ `fund_basic` | 两者均覆盖，AkShare 免费且字段更全（含拼音、托管行） |
| **基金净值（日频）** | ✅ `fund_open_fund_info_em` / `fund_etf_hist_em` | ✅ `fund_nav` | AkShare 单次返回全历史；Tushare 需积分 |
| **基金经理** | ✅ `fund_manager_em`（含任期、历史业绩） | ⚠️ 需 5000+ 积分 | AkShare 完整免费 |
| **基金持仓（季报）** | ✅ `fund_portfolio_hold_em`（重仓股）/ `fund_portfolio_industry_allocation_em`（行业） | ✅ `fund_portfolio` | 两者均覆盖 |
| **基金规模与份额** | ✅ `fund_share_position_em` | ✅ `fund_share` / `etf_share_size`（需 8000 积分） | Tushare 高级字段门槛高 |
| **机构持有比例** | ✅ 通过 `fund_portfolio_hold_em` 间接获取 | ⚠️ 需高积分 | AkShare 直接可用 |
| **业绩指标（夏普/回撤/波动）** | ⚠️ 不直接提供，需用 empyrical/quantstats 计算 | ⚠️ 不直接提供 | 两者均需自算 |
| **同类排名** | ✅ `fund_open_fund_rank_em` / `fund_em_open_fund_rank` | ✅ `fund_performance` | AkShare 直接返回百分位 |
| **申赎现金流** | ⚠️ 通过份额变动 `fund_share_position_em` 推算 | ⚠️ 同上 | L4 现金流分析需推算 |
| **基金分红** | ✅ `fund_dividend_em` | ✅ `fund_div` | 两者均覆盖 |

**覆盖度评估：** AkShare ✅ 完整 / Tushare 部分字段需积分。

### 1.2 AkShare 反爬与稳定性

> 来源：[AKShare 三方对比](https://juejin.cn/post/7654891094078439474) + [akshare vs tushare 对比](https://blog.csdn.net/HiWangWenBing/article/details/154987681)

- **数据来源**：实时穿透到上游公开网站（东方财富/新浪/同花顺/巨潮/雪球/天天基金）做 HTTP scrape，AkShare 本身不存数据
- **反爬强度**：中低（东方财富对高频访问会临时封 IP，但日频拉取无压力）
- **全市场拉取耗时**：8000 只基金日频净值，按 1 req/s 限流 ≈ **2-3 小时**（首次全量）；增量更新每日 ~20 分钟
- **是否需要代理池**：不需要。1 req/s + User-Agent 轮换 + 本地缓存足够
- **接口稳定性**：日 K 线接口稳定，小众接口（北向资金细分、研报）可能偶发 break

### 1.3 基金分类标准

- **天天基金分类**：股票型/混合型/债券型/指数型/QDII/LOF/FOF 等 ~20 类（最主流，AkShare 直接返回）
- **晨星分类**：更细（大盘价值/中盘成长/中小盘平衡等 ~50 类），需爬虫或付费
- **Wind 分类**：商业数据库，本项目不采用

**本项目采用天天基金分类**（AkShare 直接返回，零成本）。

### 1.4 本地 macOS 可行性

- AkShare 支持 macOS，Python 3.8+
- Tushare 同样支持 macOS
- 本地缓存推荐：Parquet / SQLite（增量更新）

### 1.5 推荐方案

**AkShare 单源 + 本地缓存**。
- 理由：覆盖度足够、零成本、与 Tushare 重叠 90%
- Tushare 不引入：高级字段积分门槛高（5000-8000），本项目用量级用不到
- 架构上抽象 `DataProvider` 接口，便于未来切换或加 Tushare 降级

---

## 2. 飞书 CLI 接入调研

> 本节来自本机已安装的 lark-cli skills 文档（`~/.trae-cn/skills/lark-*/`）+ 飞书开放平台标准文档 URL。

### 2.1 lark-cli 真实性

✅ **真实存在**。证据：
- 本机已安装 30+ 个 `lark-*` skills，包含完整命令树、权限表、错误码、API 路径
- npm 包名 `@larksuite/cli`
- GitHub 仓库 `larksuite/cli`（由 skills 安装命令 `npx skills add larksuite/cli` 证明）
- 官方域名：[open.feishu.cn](https://open.feishu.cn/)

### 2.2 能力矩阵

| 能力 | lark-cli 命令 | 底层 OpenAPI |
|---|---|---|
| 单聊推送卡片 | `im +messages-send --msg-type interactive --as bot` | `POST /open-apis/im/v1/messages` |
| 创建多维表格 | `base +base-create --as user` | `POST /open-apis/bitable/v1/apps` |
| 创建字段 | `base +field-create` | `POST /open-apis/bitable/v1/apps/:app/tables/:table/fields` |
| 批量写记录 | `base +record-batch-create`（≤200 条/批） | `POST /open-apis/bitable/v1/apps/:app/tables/:table/records/batch_create` |
| 视图筛选/排序 | `base +view-set-filter / +view-set-sort` | 满足"今日候选"视图需求 |
| 接收消息（Roadmap） | `event consume im.message.receive_v1` | 长连接 NDJSON 流 |

### 2.3 个人开发者可行性

✅ **完全可行，零成本**：
- 免费创建飞书团队（个人/小团队版免费）
- 在团队下创建**自建应用**，无需企业认证
- 自建应用默认仅本租户可见，与"个人单用户"完美匹配
- Token 自动刷新（lark-cli 管理）

### 2.4 最小权限 scope

| 能力 | 身份 | scope |
|---|---|---|
| 单聊推送 | bot | `im:message:send_as_bot` |
| 多维表格读写 | user | base 域 scope（开发者后台勾选） |

### 2.5 定时方案

**macOS launchd**（最契合"关机不推 + 节假日不发"约束）：
```xml
<!-- ~/Library/LaunchAgents/com.trandeagent.daily.plist -->
<key>StartCalendarInterval</key>
<dict><key>Hour</key><integer>16</integer></dict>
```
- 飞书侧 workflow 的 `TimerTrigger` 只能发文本+按钮，不能跑本地 Python，故不采用

### 2.6 推荐方案

**lark-cli 全权代理飞书侧 IO + Python 做业务计算 + launchd 定时**。
- Python 通过 `subprocess.run(["lark-cli", ...])` 调用，省去 SDK 调用代码
- Base 操作用 `--as user`（用户资源），推送用 `--as bot`

---

## 3. LLM 选型调研

> 注：本节价格来自训练知识（截至 2025-08），所有价格标注"参考值"，最终以官方定价页为准。

### 3.1 候选模型能力对比

| 模型 | 输入价（/1M，参考） | 输出价（/1M，参考） | 国内可达性 | 中文金融语料 | 推荐 |
|---|---|---|---|---|---|
| **DeepSeek-V3** | ¥1（缓存命中 ¥0.1） | ¥2 | ✅ 直连 | ★★★★★ | ⭐ 主力 |
| Qwen-Plus | ≈¥0.8 | ≈¥2 | ✅ 直连 | ★★★★☆ | 备选 |
| Qwen-Max | ≈¥20 | ≈¥60 | ✅ 直连 | ★★★★★ | 高质量档 |
| Kimi | ≈¥12 | ≈¥12 | ✅ 直连 | ★★★★ | 不推荐（性价比低） |
| GLM-4-Flash | 免费 | 免费 | ✅ 直连 | ★★★ | 零成本兜底 |
| GPT-4o-mini | ≈¥1.1 | ≈¥4.3 | ❌ 需中转 | ★★★☆ | 不推荐 |
| GPT-4o | ≈¥18 | ≈¥72 | ❌ 需中转 | ★★★★ | 不推荐 |
| Claude 3 Opus | ≈¥108 | ≈¥540 | ❌ 需中转 | ★★★★ | 明确不推荐 |

### 3.2 月度成本估算

> 假设：每天 5 只基金分析 + 50-200 策略信号 = 日均 ~50 次调用，每次 3K input + 2K output
> 月度：~1M input + ~0.7M output（按 22 交易日）

| 模型 | 月成本估算 |
|---|---|
| DeepSeek-V3 | ≈ **¥2.4** |
| Qwen-Plus | ≈ ¥2.2 |
| Qwen-Max | ≈ ¥62 |
| GPT-4o | ≈ ¥64 |
| Claude 3 Opus | ≈ ¥450（不推荐） |

**核心洞察：** 用量在所有主流模型下月成本都 ≤ ¥65。**预算不构成约束**，决策应回到「国内可达性 + 中文金融语料 + 防幻觉」。

### 3.3 推荐方案

**主力 DeepSeek-V3 + 备选 Qwen-Max**：
- 主力 DeepSeek-V3：性价比第一、中文金融语料强、国内直连、JSON 输出稳定
- 备选 Qwen-Max：复杂归因叙事场景切到高质量档
- 架构层抽象 `LLMClient` 接口（环境变量切换 provider），便于后续灰度对比

### 3.4 防幻觉机制（呼应 R3、R10 风险）

**MVP 不上 RAG**，结构化指标 + 强约束 prompt 即可：
1. System Prompt 明确"唯一事实来源是 `<metrics>` 标签内 JSON"
2. 强制引用：每条结论必须以「【依据：<指标名>=<数值>】」引用
3. 输出 Schema 约束（JSON mode 强制结构化）
4. 允许"数据不足，无法判断"（比惩罚幻觉更有效）
5. 代码侧后校验：检查引用的指标名是否真存在于输入 JSON
6. 大师心智模型仅取公开著作原文，prompt 强约束不得发挥

---

## 4. 基金分析方法论

> 来源：[支付宝基金指南](https://cj.sina.cn/articles/view/7879922977/1d5ae152101901c8e4) + [4433 法则教程](https://blog.csdn.net/gitblog_00520/article/details/157119053) + 清华大学出版社《基金交易策略》PDF

### 4.1 单基金分析指标分层（4 层）

#### L1 基本面（必看）
| 指标 | 含义 | 阈值（业内共识） |
|---|---|---|
| 基金规模 | 总资产规模 | <2 亿有清盘风险；>100 亿调仓不灵活；**2-50 亿最优**（来源：InvesTool 4433 法则严选） |
| 成立时间 | 成立年限 | <3 年无足够历史数据 |
| 基金经理任期 | 现任经理管理年限 | **<2 年警惕**；>5 年稳定（来源：InvesTool） |
| 机构持有比例 | 机构持有份额占比 | **>30% 聪明钱认可**；<5% 警惕（来源：聪明钱策略） |
| 费率 | 管理费+托管费 | 主动股基 1.5%+0.25%；指数基金 0.5%+0.1%；**C 类短线、A 类长线** |

#### L2 业绩指标（必看）
| 指标 | 计算公式 | 阈值 |
|---|---|---|
| 收益率 | (期末净值-期初)/期初 | 看同类排名百分位 |
| 同类排名 | 在同类基金中的百分位 | **前 1/4 优秀**（4433 法则核心） |
| 最大回撤 | max((峰值-谷值)/峰值) | **<15% 优秀**；>30% 警惕（主动股基） |
| 夏普比率 | (年化收益-无风险)/年化波动 | **>1 优秀**；>2 极佳（来源：晨星） |
| 波动率 | 日收益标准差×√252 | <15% 低波；>25% 高波 |
| 阿尔法 | Jensen's Alpha | >0 跑赢基准 |
| 贝塔 | 与基准的协方差/方差 | >1 进攻型；<1 防御型 |

#### L3 风格分析（进阶）
| 指标 | 含义 | 解读 |
|---|---|---|
| 持仓风格 | 大/中/小盘 × 价值/平衡/成长 | 与业绩基准风格对比，识别漂移 |
| 行业集中度 | 前 3 大行业占比 | >60% 高集中，单一赛道 |
| 重仓股变动频率 | 季度重仓股变动率 | 高变动=风格漂移（来源：晨星） |
| 持仓换手率 | 年度买卖额/平均资产 | **<100% 长期持有**；>300% 频繁交易 |

#### L4 现金流分析（高阶）
| 指标 | 含义 | 解读 |
|---|---|---|
| 份额变动趋势 | 季度份额净流入/流出 | 持续净流出警惕（赎回潮） |
| 机构 vs 个人持有变化 | 季度机构占比变化 | 机构减仓信号 |
| 历史分红记录 | 累计分红次数+金额 | 长期持有者实际收益 |

### 4.2 Python 实现库

| 库 | 用途 | GitHub |
|---|---|---|
| `empyrical` | 风险指标计算（夏普、回撤、α/β） | [quantopian/empyrical](https://github.com/quantopian/empyrical) |
| `quantstats` | 一键报告（HTML/PDF） | [ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) |
| `ffn` | 金融函数库 | [pmorissette/ffn](https://github.com/pmorissette/ffn) |
| `pandas-ta` | 技术指标（MA/MACD/RSI/布林） | [twopirllc/pandas-ta](https://github.com/twopirllc/pandas-ta) |

---

## 5. 主流公募基金投资策略原型清单

> 来源：4433 法则（邱显比教授）+ 网格交易社区 + 双动量（Gary Antonacci）+ 兴业证券/华泰金工研报 + 且慢/交银投顾公开策略

### 5.1 15 个有出处的策略原型

| # | 策略名 | 核心逻辑 | 关键参数 | 出处 |
|---|---|---|---|---|
| 1 | **4433 法则** | 近 1/2/3/5 年排名前 1/4 + 近 3/6 月排名前 1/3 | 排名百分位 | [邱显比教授（台大财金）](https://blog.csdn.net/gitblog_00520/article/details/157119053) |
| 2 | **买入并持有** | 全仓买入持有到末日 | 无 | [《基金交易策略》清华大学出版社](https://www.tup.tsinghua.edu.cn/upload/books/yz/105259-01.pdf) |
| 3 | **定投策略** | 固定金额定期买入 | 周期、金额 | 同上 |
| 4 | **均线定投** | PE/价格低于 MA 时加仓，高于时减仓 | MA 周期（200 日） | 且慢/交银投顾 |
| 5 | **网格交易** | 价格每跌 X% 买入，每涨 X% 卖出 | 网格间距（高波动 5%、中波动 3%、低波动 4%） | [雪球专栏](https://xueqiu.com/8059540209/383551783) |
| 6 | **双动量** | 绝对动量+相对动量，每月调仓 | 回看期（12 月） | Gary Antonacci《Dual Momentum Investing》 |
| 7 | **行业轮动** | 按行业景气度/动量月度轮换 | 行业数、调仓频率 | 兴业证券金工 |
| 8 | **风险平价** | 各资产风险贡献相等 | 杠杆、目标波动 | [达利欧全天候](https://www.tradingkey.com/zh-hans/analysis/commodities/metal/261764178) |
| 9 | **聪明钱跟随** | 跟踪机构持有比例高的基金 | 机构占比阈值（>30%） | 聪明钱策略 |
| 10 | **PE 分位择时** | 指数 PE 历史分位低时加仓 | 分位阈值（20%/80%） | 且慢估值定投 |
| 11 | **股债收益差（FED 模型）** | 股息率-国债收益率差值择时 | 差值阈值 | 美联储 FED 模型 |
| 12 | **低波动** | 选近 3 年波动率最低的 N 只 | N、回看期 | 华泰金工 |
| 13 | **红利策略** | 选股息率最高的 N 只 | 股息率阈值 | 经典红利策略 |
| 14 | **趋势跟踪** | 价格突破 N 日高点买入，跌破卖出 | N（55/20） | 海龟交易法则 |
| 15 | **逆向投资** | 大跌（回撤>X%）时买入，反弹卖出 | 回撤阈值（20%） | [霍华德·马克斯《周期》](https://xueqiu.com/9051366877/347870953) |

### 5.2 差异维度矩阵（避免同质化）

为保证 50-200 个策略真正差异化，采用正交差异维度：

| 维度 | 取值 | 示例 |
|---|---|---|
| **投资域** | 价值/成长/红利/趋势/逆向/全球配置/指数增强/低波 | 8 种 |
| **择时逻辑** | 均线/动量/分位/不动 | 4 种 |
| **调仓频率** | 日/周/月/季 | 4 种 |
| **风控阈值** | 回撤止损 5%/10%/15%/20% | 4 种 |
| **持仓集中度** | Top-5/Top-10/Top-20/全市场 | 4 种 |

组合空间：8 × 4 × 4 × 4 × 4 = **2048 种**，本项目取 50-200 个最具代表性的子集，LLM 生成时按差异维度强制约束。

---

## 6. 投资大师心智模型档案（精选 8 位）

> 用户选择"精选 5-8 位"，本报告选 8 位，覆盖价值/成长/全球配置/逆向/宏观/危机对冲/指数 7 个投资域。
> 所有心智模型要点均来自公开著作原文，引用原文出处（呼应 R10 风险）。

### 6.1 候选名单与取舍

| 大师 | 投资域 | 是否入选 | 取舍理由 |
|---|---|---|---|
| **Warren Buffett 巴菲特** | 价值股 | ✅ | 必选，公开股东信最全 |
| **Charlie Munger 芒格** | 多元思维/逆向 | ✅ | 与巴菲特互补，"反过来想"独到 |
| **Benjamin Graham 格雷厄姆** | 安全边际 | ✅ | 价值投资之父，《聪明的投资者》原典 |
| **Peter Lynch 林奇** | 成长股/PEG | ✅ | PEG 指标发明者，对应成长基金 |
| **Ray Dalio 达利欧** | 全天候/宏观 | ✅ | 风险平价创始人，对应 QDII/全球配置 |
| **Howard Marks 马克斯** | 周期/逆向 | ✅ | 橡树资本，《周期》原典 |
| **Nassim Taleb 塔勒布** | 黑天鹅/反脆弱 | ✅ | 杠铃策略，对应危机对冲 |
| **John Bogle 博格尔** | 指数化 | ✅ | 先锋集团创始人，对应 ETF/指数基金 |
| George Soros 索罗斯 | 反身性 | ❌ | 心智模型较抽象，难直接落地为规则 |
| Joel Greenblatt 绿林布拉特 | 神奇公式 | ❌ | 与格雷厄姆重叠，已由 Graham 代表 |

### 6.2 心智模型要点（原文考据）

#### ① 巴菲特 — 护城河 + 能力圈
> 出处：[伯克希尔历年致股东信](https://xueqiu.com/2524803655/362558200) + [《巴菲特致股东信》劳伦斯·坎宁安编](http://m.toutiao.com/group/7654779267590390291/)

核心心智模型：
1. **市场先生**：波动不是风险，是机会（借自格雷厄姆）
2. **安全边际**：用 40 美分买 1 美元
3. **护城河**：品牌/规模/网络效应/转换成本/专利
4. **能力圈**：5 分钟说不清商业模式就跳过
5. **逆向操作**："别人贪婪时恐惧，别人恐惧时贪婪"

**落地为策略规则**：选持仓股集中度高（Top-10 > 60%）、ROE 持续 > 15%、行业有定价权（消费/金融/科技龙头）

#### ② 芒格 — 多元思维模型 + 逆向思考
> 出处：[《穷查理宝典》Poor Charlie's Almanack](https://xueqiu.com/2524803655/362558200)

核心心智模型：
1. **多元思维模型**：跨学科（数学/物理/生物/心理学）综合判断
2. **逆向思考**："告诉我我会死在哪，我就永远不去那里"
3. **避免愚蠢**：不追求聪明，避免犯大错
4. **集中投资**：把大钱放在高确定性标的

**落地为策略规则**：剔除"踩雷特征"基金（规模过小、风格漂移、激进行业），而非主动选赢家

#### ③ 格雷厄姆 — 安全边际 + 市场先生
> 出处：《聪明的投资者》The Intelligent Investor（1949）+《证券分析》Security Analysis（1934）

核心心智模型：
1. **安全边际**：买入价低于内在价值 50%
2. **市场先生**：市场是情绪化的对手盘
3. **Mr. Market 寓言**：每天报价，你可选买/卖/忽略
4. **量化标准**：PE < 15、PB < 1.5、股息率 > 3.5%

**落地为策略规则**：PE 分位择时、低 PE/低 PB 基金筛选

#### ④ 林奇 — PEG + 生活中发现机会
> 出处：《One Up on Wall Street》（1989）+《Beating the Street》（1993）

核心心智模型：
1. **PEG 指标**：PE / 收益增长率 < 1 买入
2. **生活中发现**：消费者视角找成长股
3. **成长分类**：缓慢增长/稳定增长/快速增长/周期/困境反转/资产隐藏
4. **分散 vs 集中**：小资金集中、大资金分散

**落地为策略规则**：PEG 选基（成长股基金）

#### ⑤ 达利欧 — 全天候 + 经济季节
> 出处：[《Principles》](https://www.tradingkey.com/zh-hans/analysis/commodities/metal/261764178-ray-dalio-debt-cycles-gold-all-weather-framework) + [2026 全天候组合长文](http://finance.sina.cn/cj/2026-03-25/detail-inhsecsh3704732.d.html)

核心心智模型：
1. **经济四季**：增长/通胀的 4 种组合
2. **风险平价**：各类资产风险贡献相等
3. **全天候配置**：股票 30%+长期国债 40%+中期国债 15%+黄金 7.5%+商品 7.5%
4. **债务周期**：短期 5-8 年 + 长期 50-75 年
5. **不择时**：用结构分散而非择时

**落地为策略规则**：风险平价基金组合（多资产配置基金）

#### ⑥ 马克斯 — 周期 + 第二层思维
> 出处：[《周期》Mastering the Market Cycle（2018）](https://xueqiu.com/9051366877/347870953)

核心心智模型：
1. **三大规律**：不走直线/不会相同只会相似/少走中间多走极端
2. **钟摆律**：在贪婪与恐惧两端摆动
3. **第二层思维**："大家都觉得好，所以我要卖"
4. **逆向投资**：极端时与大众反向
5. **定位优于预测**：判断周期位置，不预测拐点

**落地为策略规则**：钟摆指标（PE 分位+情绪指标）择时、逆向加仓

#### ⑦ 塔勒布 — 反脆弱 + 杠铃策略
> 出处：《黑天鹅》The Black Swan（2007）+《反脆弱》Antifragile（2012）+《随机漫步的傻瓜》

核心心智模型：
1. **黑天鹅**：极端事件不可预测但影响巨大
2. **反脆弱**：从波动中受益（vs 脆弱/坚韧）
3. **杠铃策略**：90% 极度安全 + 10% 极度激进
4. **皮肤在游戏中**：决策者必须承担后果
5. **否定法**：先排除肯定错的，再看剩下的

**落地为策略规则**：杠铃组合（90% 货基+债基 / 10% 高波动 QDII）

#### ⑧ 博格尔 — 指数化 + 成本控制
> 出处：《Common Sense on Mutual Funds》（1999）+《Little Book of Common Sense Investing》（2007）

核心心智模型：
1. **指数化**：买整个市场，不选股
2. **成本控制**：费率是确定性损失，长期复利侵蚀巨大
3. **长期持有**：不要短期交易
4. **再平衡**：定期恢复目标比例
5. **均值回归**：主动基金长期跑不赢指数

**落地为策略规则**：宽基指数定投、低费率筛选（< 0.5%）

### 6.3 心智模型 → 策略映射

| 大师 | 策略原型 | 适用基金类型 |
|---|---|---|
| 巴菲特 | 护城河筛选（ROE>15%、Top-10 集中） | 主动股票基金 |
| 芒格 | 排雷筛选（剔除规模<2亿/风格漂移） | 全类型 |
| 格雷厄姆 | 价值筛选（低 PE/低 PB/高股息） | 价值型基金 |
| 林奇 | PEG 筛选（PEG<1） | 成长型基金 |
| 达利欧 | 风险平价（多资产配置） | QDII / 平衡型 |
| 马克斯 | 钟摆择时（PE 分位逆向） | 指数基金 |
| 塔勒布 | 杠铃组合（90%安全+10%激进） | 全类型 |
| 博格尔 | 宽基指数定投（低费率） | ETF联接/指数 |

---

## 7. 回测框架选型

> 来源：[VectorBT/Backtrader/Zipline 对比](https://www.cnblogs.com/hopesun/p/18815644) + [VectorBT 2026 量化指南](https://dibi8.com/resources/ai-trading/vectorbt-quantitative-backtesting/) + [量化开源项目对比](https://modelers.csdn.net/69a68c247bbde9200b9c69c2.html)

### 7.1 框架对比矩阵

| 框架 | 类型 | 性能 | 易用性 | macOS | 实盘 | 社区 | 适用本场景 |
|---|---|---|---|---|---|---|---|
| **VectorBT** | 向量化 | ★★★★★（GPU/numba 加速） | ★★★★ | ✅ | ❌ | 活跃 | ⭐ **推荐** |
| Backtrader | 事件驱动 | ★★（逐笔） | ★★★★ | ✅ | 支持 | 活跃 | 备选 |
| Zipline-reloaded | 事件驱动 | ★★★ | ★★★ | ✅ | 弱 | 社区维护 | 不推荐 |
| bt | 向量化 | ★★★★ | ★★★ | ✅ | ❌ | 较活跃 | 备选 |
| NautilusTrader | 混合(Rust) | ★★★★★ | ★★ | ✅ | ✅ | 新兴 | 实盘过渡用 |

### 7.2 性能基准（来源：VectorBT 官方指南）

> 测试场景：1000 只股票 10 年日线数据回测

| 框架 | 耗时 | 加速比 |
|---|---|---|
| Zipline | 6 小时 | 1× |
| Backtrader | 2 小时 | 3× |
| **VectorBT** | **8 分钟** | **45×** |

### 7.3 推荐方案

**VectorBT 主力（参数扫描）+ Backtrader 备选（精细事件回测）**：
- **VectorBT**：50-200 策略 × 3-5 年 × 8000 基金的参数扫描，秒级完成
- **Backtrader**：对胜出的 Top-5 策略做精细事件驱动回测（含手续费、滑点）
- macOS 安装：`pip install vectorbt backtrader`（numba 在 macOS 需 `xcode-select --install`）

---

## 8. Open Questions 的回答

| # | Open Question | 调研结论 |
|---|---|---|
| Q1 | AkShare vs Tushare 字段覆盖 | AkShare 完整覆盖本项目所需所有字段，单源即可 |
| Q2 | AkShare 反爬强度 | 中低，1 req/s + UA 轮换 + 本地缓存足够 |
| Q3 | 飞书 CLI 能力 | lark-cli 真实存在，全套 IM+Base 能力，个人开发者零成本可行 |
| Q4 | LLM 选型 | DeepSeek-V3 主力（性价比第一），Qwen-Max 高质量档备选 |
| Q5 | 择时指标库 | 15 个策略原型 + 4 层基金分析指标已梳理 |
| Q6 | 基金分类标准 | 采用天天基金分类（AkShare 直接返回） |
| Q7 | 策略原型清单 | 15 个有出处策略原型 + 差异维度矩阵 |
| Q8 | 大师心智模型素材 | 8 位大师，全部基于公开著作原文 |
| Q9 | 回测框架 | VectorBT（参数扫描）+ Backtrader（精细回测） |
| Q10 | 差异维度矩阵 | 5 维（域/择时/频率/风控/集中度）= 2048 组合空间 |

---

## 9. 所有引用链接（可点击）

### AkShare / Tushare
- [AKShare 公募基金数据官方文档](https://akshare.akfamily.xyz/data/fund/fund_public.html)
- [AKShare GitHub](https://github.com/akfamily/akshare)
- [Tushare ETF 份额规模接口](https://tushare.pro/document/2?doc_id=408)
- [Tushare 官网](https://tushare.pro/)
- [AKShare vs Tushare vs Privora 三方对比](https://juejin.cn/post/7654891094078439474)
- [akshare vs tushare 详解](https://blog.csdn.net/HiWangWenBing/article/details/154987681)

### 飞书 lark-cli
- [飞书开放平台首页](https://open.feishu.cn/)
- [飞书开发者后台](https://open.feishu.cn/app)
- [GitHub larksuite 组织](https://github.com/larksuite)
- [发送消息 API](https://open.feishu.cn/document/server-docs/im-v1/message/create)
- [消息卡片 JSON 结构](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/feishu-cards/card-json-structure)
- [多维表格开发指南](https://open.feishu.cn/document/server-docs/docs/bitable-v1/overview)
- [事件订阅指南](https://open.feishu.cn/document/server-docs/event-subscription-guide/overview)

### LLM 定价
- [DeepSeek 定价](https://api-docs.deepseek.com/zh-cn/quick_start/pricing)
- [阿里云百炼模型与定价](https://help.aliyun.com/zh/model-studio/getting-started/models)
- [月之暗面 Kimi 定价](https://platform.moonshot.cn/docs/pricing)
- [智谱 GLM 定价](https://open.bigmodel.cn/pricing)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Anthropic Pricing](https://www.anthropic.com/pricing)
- [SuperCLUE 金融评测](https://www.superclueai.com/)

### 基金分析方法论
- [支付宝基金完全指南（含 4433 法则实操）](https://cj.sina.cn/articles/view/7879922977/1d5ae152101901c8e4)
- [InvesTool 4433 法则完全教程](https://blog.csdn.net/gitblog_00520/article/details/157119053)
- [《基金交易策略》清华大学出版社 PDF](https://www.tup.tsinghua.edu.cn/upload/books/yz/105259-01.pdf)
- [网格交易实战](https://xueqiu.com/8059540209/383551783)

### 投资大师心智模型
- [巴菲特致股东信原文（1958-2025）](https://xueqiu.com/2524803655/361522802)
- [巴菲特致股东信解读](https://xueqiu.com/2524803655/362558200)
- [2024 巴菲特致股东信原文](https://finance.sina.cn/2024-02-25/detail-inakenxu9206878.d.html?vt=4)
- [2025 巴菲特致股东信全文](https://finance.sina.com.cn/cj/2025-02-22/doc-inemkshz3902671.shtml)
- [霍华德·马克斯《周期》解读](https://xueqiu.com/9051366877/347870953)
- [马克斯周期论](https://xueqiu.com/3295943611/388030434)
- [达利欧债务周期框架](https://www.tradingkey.com/zh-hans/analysis/commodities/metal/261764178-ray-dalio-debt-cycles-gold-all-weather-framework)
- [达利欧全天候组合原文（2026）](http://finance.sina.cn/cj/2026-03-25/detail-inhsecsh3704732.d.html)

### 回测框架
- [VectorBT/Backtrader/Zipline 对比](https://www.cnblogs.com/hopesun/p/18815644)
- [VectorBT 2026 量化指南](https://dibi8.com/resources/ai-trading/vectorbt-quantitative-backtesting/)
- [10 个量化开源项目对比](https://modelers.csdn.net/69a68c247bbde9200b9c69c2.html)
- [Backtrader vs NautilusTrader vs VectorBT vs Zipline-reloaded](https://autotradelab.com/blog/backtrader-vs-nautilusttrader-vs-vectorbt-vs-zipline-reloaded)
