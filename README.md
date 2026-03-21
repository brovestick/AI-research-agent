# Research Agent

A 股投研 Native 工作流系统，面向 Claude Code 宿主代理。系统包含 5 个独立工作流、17 个可复用知识节点和 6 个 MOC 导航文件，覆盖从主题选股到个股深度研报的完整投研链条。

Python 不调用任何大模型 API，只负责数据处理、状态持久化和文件生成。研究分析由宿主代理通过 `skills/` 执行。

---

## 一、整体架构

系统分为三层：

```
┌─────────────────────────────────────────────────────────┐
│  导航层 — skills/_moc/                                    │
│  INDEX.md → 各工作流 MOC（模块构成、执行顺序、知识引用）          │
├─────────────────────────────────────────────────────────┤
│  知识层 — skills/_knowledge/                               │
│  conventions/（5 个通用约定）+ frameworks/（12 个分析框架）      │
├─────────────────────────────────────────────────────────┤
│  执行层 — 5 个工作流                                        │
│  撰写报告 · 公司尽调 · 一页纸 · 主题选股 · 行业研究（占位）       │
└─────────────────────────────────────────────────────────┘
```

设计原则：

- Python 不负责"思考"，Agent 不负责"记状态"
- 所有状态以磁盘上的 `run_state.json` 为准
- 所有下一步命令写死在 Skill 里，不允许 Agent 自己猜
- 知识节点被多个工作流复用，通过 MOC 的 wikilinks 引用

---

## 二、目录结构

```
research_agent/
├── main.py                          # CLI 入口
├── config.py                        # 配置与模块注册
├── requirements.txt
│
├── skills/
│   ├── _knowledge/                  # 可复用知识节点
│   │   ├── conventions/             #   5 个通用约定
│   │   │   ├── data-sourcing.md
│   │   │   ├── data-timeliness.md
│   │   │   ├── observable-indicators.md
│   │   │   ├── uncertainty-labeling.md
│   │   │   └── web-search-priority.md
│   │   └── frameworks/              #   12 个分析框架
│   │       ├── bull-bear-divergence.md
│   │       ├── catalyst-format.md
│   │       ├── competitive-landscape.md
│   │       ├── cyclical-vs-growth.md
│   │       ├── financial-metrics-table.md
│   │       ├── industry-lifecycle.md
│   │       ├── pricing-power.md
│   │       ├── product-line-breakdown.md
│   │       ├── supply-demand-elasticity.md
│   │       ├── three-scenario-assumption.md
│   │       ├── valuation-assessment.md
│   │       └── value-chain-bargaining.md
│   │
│   ├── _moc/                        # 导航层（Maps of Content）
│   │   ├── INDEX.md                 #   总索引 + 交叉引用矩阵
│   │   ├── research-report.md       #   个股深度研报
│   │   ├── due-diligence.md         #   公司尽调
│   │   ├── one-pager.md             #   一页纸
│   │   ├── theme-stock-picking.md   #   主题选股
│   │   └── industry-research.md     #   行业研究（占位）
│   │
│   ├── research-agent-orchestrator/ # 撰写报告总控 Skill
│   ├── research-module-01~06/       # 撰写报告 6 模块 Skill + Prompt
│   ├── extract-IR/                  # IR 材料提取 Skill
│   ├── company-due-diligence/       # 公司尽调工作流定义
│   │   ├── SKILL.md
│   │   ├── retrieval_strategy.md
│   │   └── report_requirements.md
│   ├── company-one-pager/           # 一页纸工作流定义
│   │   ├── SKILL.md
│   │   ├── retrieval_strategy.md
│   │   └── output_format.md
│   └── theme-stock-picking/         # 主题选股工作流定义
│       ├── SKILL.md
│       ├── user_query_format.md
│       ├── sub_query_generation.md
│       ├── reflection_and_planning.md
│       └── report_generation.md
│
├── docs/                            # 参考文档与领域笔记
│   ├── style_samples.md
│   ├── output_schema_reference.json
│   ├── user_data获取.xlsx
│   └── domain-notes/               #   领域研究笔记
│       ├── 光模块/
│       └── 快速问答.md
│
├── modules/                         # 撰写报告数据处理模块
│   ├── 01_classify.py               #   行业定性
│   ├── 02_business.py               #   商业模式分析
│   ├── 03_financial.py              #   财务分析
│   ├── 04_valuation.py              #   估值建模
│   ├── 05_risk.py                   #   风险梳理
│   └── 06_catalyst.py               #   催化剂与时间窗口
│
├── utils/                           # 公共工具
│   ├── state_manager.py             #   run_state.json 读写
│   ├── pdf_reader.py                #   PDF 读取
│   ├── user_data_parser.py          #   user_data.csv 解析
│   ├── excel_writer.py              #   估值模板 XLSX 生成
│   ├── prompt_loader.py             #   Prompt 模板渲染
│   └── annual_report_downloader.py  #   年报下载
│
├── tools/                           # 预处理工具
│   ├── pdf_extract.py               #   PDF 定向页面提取
│   ├── annrpt_extract.py            #   年报智能提取（Qwen）
│   ├── broker_rpt_extract.py        #   券商研报结构化提取（Qwen）
│   └── extract_IR.py                #   IR 材料提取
│
├── companies/{code}_{name}/         # 公司数据目录
│   ├── user_data.csv                #   必填：公司名称+代码+补充数据
│   ├── financial_data/              #   iFinD 导出的 XLSX
│   ├── raw/                         #   原始 PDF
│   │   ├── annual_reports/
│   │   ├── broker_reports/
│   │   ├── announcements/
│   │   └── IR/
│   ├── processed/                   #   结构化 MD（由预处理 Skill 产出）
│   │   ├── annual_reports/
│   │   ├── broker_reports/
│   │   ├── announcements/
│   │   └── IR/
│   ├── report.md                    #   撰写报告最终产出
│   └── 估值模板.xlsx                  #   撰写报告最终产出
│
└── output/
    └── .runs/{run_id}/              # 撰写报告运行中间状态
```

---

## 三、知识层

`skills/_knowledge/` 下的 17 个知识节点被多个工作流复用。

### Conventions（5 个通用约定）

适用于所有工作流，规范数据处理行为。

| 节点 | 说明 |
|------|------|
| data-sourcing | 数据来源优先级与标注规范 |
| data-timeliness | 时效性要求与过期提示 |
| uncertainty-labeling | 不确定性标注（已验证 / 估测 / 无依据） |
| web-search-priority | 联网检索优先原则 |
| observable-indicators | 可观测指标绑定规范 |

### Frameworks（12 个分析框架）

按语义分为 4 组，各工作流按需引用。

| 分组 | 节点 |
|------|------|
| 行业分析 | cyclical-vs-growth, industry-lifecycle, competitive-landscape, supply-demand-elasticity |
| 公司分析 | product-line-breakdown, pricing-power, value-chain-bargaining, financial-metrics-table |
| 估值与预测 | three-scenario-assumption, valuation-assessment |
| 市场观点 | bull-bear-divergence, catalyst-format, observable-indicators |

---

## 四、导航层

`skills/_moc/` 下的 6 个 MOC 文件描述每个工作流的模块构成、执行顺序和知识节点引用关系。

- `INDEX.md`：总索引，含工作流总览表和节点 × 工作流交叉引用矩阵
- 各工作流 MOC：模块详情、执行方式、引用的 frameworks/conventions

MOC 通过 `[[wikilink]]` 引用知识节点，便于 Obsidian 等工具可视化导航。

---

## 五、工作流总览

| 工作流 | Skill 命令 | 状态 | 产出 |
|--------|-----------|------|------|
| 个股深度研报 | `/撰写报告` | 已上线 | report.md + 估值模板.xlsx |
| 公司尽调 | 手动触发 | 已上线 | 投资决策备忘录（KIQ） |
| 一页纸 | 手动触发 | 已上线 | 一页纸决策备忘录 |
| 主题选股 | 手动触发 | 已上线 | 选股报告（30-40 标的） |
| 行业研究 | — | 占位 | 待定义 |

### 数据预处理 Skill

| Skill 命令 | 功能 | 输入 → 输出 |
|-----------|------|------------|
| `/登记材料` | 年报/公告/IR 材料提取 | raw/ PDF → processed/ MD |
| `/深度研报` | 券商研报结构化提取 | raw/broker_reports/ PDF → processed/broker_reports/ JSON + MD |
| `/提取IR` | IR 材料提取 | raw/IR/ PDF → processed/IR/ MD |

### 数据流

```
用户 → raw/ 放 PDF + financial_data/ 放 XLSX + 填 user_data.csv
         ↓
/登记材料 + /深度研报 + /提取IR → processed/ 下的结构化 MD
         ↓
/撰写报告 → 6 模块流水线（只读 processed/ + financial_data/ + user_data.csv）
         ↓
report.md + 估值模板.xlsx → 写入公司目录
```

---

## 六、个股深度研报（/撰写报告）

这是最完整的流水线工作流，由 6 个模块组成，通过 Python 状态机驱动。

### 6.1 执行流程

```
01 行业定性 → 02 商业模式 → 03 财务分析 → [审批] → 04 估值建模 → 05 风险分析 → 06 催化剂
  子进程        子进程      主context+审批            主context     主context     主context
```

Session 分段：

- **Session 1**：01（子进程）→ 02（子进程）→ 03（主 context）→ 展示 financial_review → 等待 `approve`
- **Session 2**：`approve` → 04 → 05 → 06 → finalize

### 6.2 模块职责

`modules/` 下的 6 个模块都是纯数据处理器，不调用模型。每个模块实现：

```python
def prepare(context, run_state) -> dict   # 读取数据 → 渲染 Prompt
def apply(context, run_state, answer) -> dict  # 解析回答 → 更新 context
```

### 6.3 Native 命令

```bash
# 创建公司目录骨架
python main.py native init-company 688102_斯瑞新材

# 初始化研究任务（从 user_data.csv 读取公司信息）
python main.py native init --company-dir "companies/688102_斯瑞新材"

# 构建模块 Prompt
python main.py native build --run-id {run_id} --module {01-06}

# 应用模块回答
python main.py native apply --run-id {run_id} --module {01-06} --answer-file {path}

# 审批放行（仅模块③后）
python main.py native approve --run-id {run_id} --checkpoint financial_review --value approve

# 生成最终产物
python main.py native finalize --run-id {run_id}
```

### 6.4 审批门禁

模块③是唯一人工检查点。`apply()` 完成后生成 `financial_review.md`，状态设为 `approval_required = true`，阻止模块④执行。只有用户精确回复 `approve`（区分大小写）才能解锁。`好`/`继续`/`ok`/`OK`/`approved`/空输入一律拒绝。

### 6.5 状态文件

唯一可信状态：`output/.runs/{run_id}/run_state.json`

关键字段：`status`, `current_module`, `next_module`, `pending_review`, `approval_required`, `approved_checkpoints`, `context`, `sections`, `artifacts`

每次 `build()` 从磁盘读状态，每次 `apply()` 完成立即落盘。即使对话上下文截断，任务仍可恢复。

### 6.6 用户预填数据

在公司目录下填写 `user_data.csv`（两列结构：`field`, `value`），`native init` 自动读取。

| 字段 | 含义 | 格式 | 必填 |
|------|------|------|------|
| company | 公司名称 | 文本 | 是 |
| code | 股票代码 | 文本 | 是 |
| price | 当前股价（元） | 数字 | 否 |
| shares | 总股本（亿股） | 数字 | 否 |
| industry_type | 行业类型预判 | growth / cyclical | 否 |
| materials | 主要原材料 | 逗号分隔 | 否 |
| comps | 可比公司 | 名称:代码,名称:代码 | 否 |
| consensus | 一致预期 EPS | 年份E:EPS,年份E:EPS | 否 |
| material_prices | 原材料价格数据路径 | 路径 | 否 |

预填数据以 blockquote 提示形式注入 Prompt，引导 Agent 验证或直接使用，未提供的字段不影响流程。

### 6.7 输出文件

运行中间产物（`output/.runs/{run_id}/`）：

- `*.prompt.md` — 模块 Prompt
- `*.answer.md` — Agent 回答
- `*.md` — 模块输出
- `*.meta.json` — 执行元数据
- `financial_review.md` — 审批检查点
- `run_state.json` — 状态机
- `context.final.json` — 最终 context 快照

最终交付产物（写入公司目录）：

- `report.md` — 完整研报
- `估值模板.xlsx` — 估值模板

---

## 七、其他工作流

### 7.1 公司尽调

来源：`skills/company-due-diligence/`（SKILL.md + retrieval_strategy.md + report_requirements.md）

2 阶段串行：6 维信息检索（短期热点、经营情况、竞争环境、财务指标、资本市场动作、市场预期）→ 报告生成（形成多空论点 → 提炼 3-5 个 KIQ → 输出决策备忘录）。

### 7.2 一页纸

来源：`skills/company-one-pager/`（SKILL.md + retrieval_strategy.md + output_format.md）

5 Section 严格串行，每 Section 完成"检索 → 分析 → 输出"闭环：公司近况（2 查询）→ 核心投资逻辑（5 查询）→ 未来事件与跟踪指标（3 查询）→ 业务拆分（4 查询）→ 财务与估值快照（4-6 查询）。

### 7.3 主题选股

来源：`skills/theme-stock-picking/`（SKILL.md + 4 个 .md）

3 阶段：研究准备（格式化问题 → 生成 4 计划 → 拆解子查询）→ 数据检索（Plan1 产业链 / Plan2 上市公司 / Plan3 市场趋势，3 个 Plan 并行）→ 报告生成（Plan4 整合为主题概述 + Mermaid 图谱 + 30-40 标的选股表）。

### 7.4 行业研究

状态：占位。模块骨架 IR-01~04 待定义。

---

## 八、Skill 设计：MOC + Knowledge 架构

系统采用 **MOC（Maps of Content）+ Knowledge** 的渐进式披露架构，替代单一大型 Skill 文件。Agent 按需加载知识节点，而非一次性读取全部内容，节省 token 和时间。

### 8.1 架构原理

```
Agent 接到任务
  │
  ├─ Session 开始 → 读 MOC（research-report.md）建立全局视图
  │
  ├─ 进入模块 → 读 SKILL.md「知识加载」section → 逐一 Read 列出的知识节点
  │
  ├─ 遇到 [[wikilink]] → 按需跟进到对应知识文件（可选，不强制递归）
  │
  └─ 执行分析 → prompt + 框架 + 联网搜索 → 写回答
```

核心优势：每个模块只加载 2-5 个相关知识节点（而非 17 个全量），子进程模块（01-02）不读 MOC，进一步精简。

### 8.2 Wikilink 解析规则

Prompt、MOC 和知识节点中的 `[[node-name]]` 引用按以下路径查找：

- `skills/_knowledge/frameworks/node-name.md`
- `skills/_knowledge/conventions/node-name.md`

### 8.3 知识加载协议

**Session 级全局定向**：每个 Session 开始（或恢复中断任务）时，主 context 读取对应工作流的 MOC 文件建立全局视图。例如撰写报告工作流读取 `skills/_moc/research-report.md`，获取 6 模块构成、知识节点映射和依赖关系。

**Module 级按需加载**：每个模块 SKILL.md 的「知识加载」section 显式列出该模块需要的知识节点文件。Agent 执行前逐一 Read 这些文件，作为分析框架上下文。

各模块引用的知识节点：

| 模块 | 知识节点 |
|------|---------|
| 01 行业定性 | cyclical-vs-growth, industry-lifecycle, competitive-landscape |
| 02 商业模式 | product-line-breakdown, competitive-landscape, value-chain-bargaining, supply-demand-elasticity, pricing-power |
| 03 财务分析 | financial-metrics-table, product-line-breakdown |
| 04 估值建模 | three-scenario-assumption, product-line-breakdown, valuation-assessment, observable-indicators |
| 05 风险分析 | competitive-landscape, bull-bear-divergence, observable-indicators |
| 06 催化剂 | catalyst-format, bull-bear-divergence, observable-indicators |

**Conventions 处理**：5 个 convention 节点的核心规则已嵌入全局 CLAUDE.md（数据可信度层级、标注方式、搜索优先级）。模块执行时不强制读取 convention 节点——CLAUDE.md 覆盖基础规范，knowledge convention 节点作为深度参考按需读取。

### 8.4 总控 Skill

`skills/research-agent-orchestrator/SKILL.md`：启动或恢复 run，指导执行循环，定义知识加载协议。

### 8.5 模块 Skill

每个模块 Skill 包含三部分内容：

1. **知识加载列表** — 执行前需要 Read 的知识节点文件
2. **读写路径** — Prompt 输入路径和回答输出路径
3. **末尾固定命令** — apply + build 下一模块（或 finalize）

Agent 不需要记住全流程，只需执行 Skill 末尾的固定命令。

模块③ Skill 特殊规则：先 `apply` → 展示 `financial_review.md` → 等待精确 `approve` → 才执行 `approve` + `build --module 04`。

### 8.6 Prompt 维护

修改位置：`skills/research-module-XX/references/prompt.md`

维护规则：
- Prompt 新增占位符 → 同步修改对应模块 `prepare()` 参数映射
- 模块新增知识节点依赖 → 同步修改 SKILL.md「知识加载」section + MOC 中的节点映射

---

## 九、预处理工具

| 工具 | 用途 | 模型 |
|------|------|------|
| `tools/annrpt_extract.py` | 年报智能提取 → 结构化 MD | Qwen3.5-plus（DashScope） |
| `tools/broker_rpt_extract.py` | 券商研报提取 → JSON → MD | Qwen3.5-plus（DashScope） |
| `tools/pdf_extract.py` | PDF 定向页面提取 | 无（纯文本提取） |
| `tools/extract_IR.py` | IR 材料提取 | — |

环境变量：`DASHSCOPE_API_KEY`，base_url：`https://dashscope.aliyuncs.com/compatible-mode/v1`

---

## 十、常见维护任务

### 修改 Prompt 变量

必须同时改两处：`skills/.../references/prompt.md` + 对应模块 `prepare()` 参数映射。

### 新增 / 修改知识节点

必须同时改：
- `skills/_knowledge/` 下对应 MD 文件（YAML frontmatter 的 `applies-to` 和 `related` 字段）
- 引用该节点的模块 SKILL.md「知识加载」section
- `skills/_moc/` 下对应工作流 MOC 的节点映射
- `skills/_moc/INDEX.md` 交叉引用矩阵

### 新增检查点

必须同时改：`main.py` 状态机 + `run_state.json` 字段 + 对应模块 Skill 末尾命令。

### 修改模块顺序

必须同时改：`config.MODULE_ORDER` + 各模块 Skill 的下一条命令 + `main.py` 校验逻辑。

### 恢复中断任务

先读 `run_state.json`，看 `status`、`next_module`、`approval_required`、`pending_review`，按状态恢复，不凭记忆。

---

## 十一、环境与验证

Python 解释器：`/opt/anaconda3/bin/python3`

修改后最低验证：

```bash
python3 -m py_compile main.py config.py utils/*.py modules/*.py
```

确认：`native build` 写出 Prompt/Meta → `native apply` 更新 `run_state.json` → 模块③生成 `financial_review.md` → 未审批前模块④不可执行 → 只有精确 `approve` 解锁 → `native finalize` 生成研报和 Excel。
