# 个股深度研报

> 来源：`skills/research-module-01~06/` | 状态：已上线

## 概述

6 模块流水线，产出一份完整的个股深度研究报告。模块 01-02 通过 Agent 子进程执行（prompt 和搜索结果不占主 context），模块 03 需审批门禁，模块 04-06 在主 context 直接执行。

## 模块构成与执行顺序

```
01 行业定性 ──→ 02 商业模式 ──→ 03 财务分析 ──→ [审批] ──→ 04 估值建模 ──→ 05 风险分析 ──→ 06 催化剂
  子进程          子进程        主context+审批              主context       主context       主context
```

### Session 分段

- **Session 1**：01（子进程）→ 02（子进程）→ 03（主 context）→ 展示 financial_review → 等待 `approve`
- **Session 2**：`approve` → 04 → 05 → 06 → finalize

---

## 模块详情

### 模块 01：行业定性分析

| 项目 | 说明 |
|------|------|
| 执行方式 | Agent 子进程 |
| 核心任务 | 行业分类定位、周期 vs 成长判断（决定下游估值方法）、政策与板块环境、行业发展阶段评估 |
| 数据来源 | 年报 MD&A、券商研报、招股说明书 + 联网检索 |
| 下游依赖 | 模块 04 根据周期/成长分类选择 PB 或 PE/PEG 估值 |

**引用的知识节点：**
- [[cyclical-vs-growth]] — 周期 vs 成长定性判断
- [[industry-lifecycle]] — 行业生命周期阶段
- [[competitive-landscape]] — 行业竞争格局概览

### 模块 02：商业模式分析

| 项目 | 说明 |
|------|------|
| 执行方式 | Agent 子进程 |
| 核心任务 | 核心业务与产品矩阵、市场结构与竞争定位、定价机制、议价力与供需弹性 |
| 数据来源 | 年报、券商研报、行业报告、招股说明书 + 雪球/巨潮搜索 |

**引用的知识节点：**
- [[product-line-breakdown]] — 产品线收入与毛利拆分
- [[competitive-landscape]] — 市场份额与竞争对手定位
- [[value-chain-bargaining]] — 上下游议价力分析
- [[supply-demand-elasticity]] — 供需弹性与价格传导
- [[pricing-power]] — 定价权与成本转嫁能力

### 模块 03：财务分析

| 项目 | 说明 |
|------|------|
| 执行方式 | 主 context（含审批门禁） |
| 核心任务 | 合并报表健康度（3 年趋势）、产品线收入与毛利分析、成本结构分析、产能利用率 |
| 数据来源 | 公司财务数据（XLSX）、联网搜索原材料价格与行业基准 |
| 审批 | 产出 `financial_review.md`，用户精确回复 `approve` 后方可继续 |

**引用的知识节点：**
- [[financial-metrics-table]] — 财务指标体系（三表、运营效率、资本结构）
- [[product-line-breakdown]] — 产品线拆分（收入增长曲线、毛利趋势）

### 模块 04：估值建模

| 项目 | 说明 |
|------|------|
| 执行方式 | 主 context |
| 核心任务 | 市场看多逻辑梳理、三情景产品线分析（量/价/利）、三年财务预测、可比公司估值基准 |
| 数据来源 | 模块 01-03 产出 + 联网搜索最新券商研报与一致预期 |
| 上游依赖 | 模块 01 的周期/成长分类决定估值方法（PB vs PE/PEG） |

**引用的知识节点：**
- [[three-scenario-assumption]] — 乐观/中性/悲观三情景假设
- [[product-line-breakdown]] — 产品线收入驱动因子拆解
- [[valuation-assessment]] — 估值方法选择与可比公司基准
- [[observable-indicators]] — 每个情景假设绑定可观测前瞻指标
- [[causal-chain-reasoning]] — 增速假设须展示完整因果链

### 模块 05：风险分析

| 项目 | 说明 |
|------|------|
| 执行方式 | 主 context |
| 核心任务 | 行业/板块风险（2-4 项）、公司层面风险（3-5 项）、估值风险 |
| 格式要求 | 每条风险包含描述（2-3 句）+ 可观测预警信号 |
| 数据来源 | 年报风险披露、雪球论坛、财经媒体 + 联网搜索 |

**引用的知识节点：**
- [[competitive-landscape]] — 竞争加剧与产能过剩风险
- [[bull-bear-divergence]] — 市场多空分歧中的风险因子
- [[observable-indicators]] — 风险预警信号绑定可观测数据

### 模块 06：催化剂分析

| 项目 | 说明 |
|------|------|
| 执行方式 | 主 context |
| 核心任务 | 市场共识与分歧、近期催化剂（6-12 月，3-5 项）、上游前瞻指标、交易时机参考 |
| 数据来源 | 最新公告、行业动态、雪球论坛、券商最新评级 + 联网搜索 |

**引用的知识节点：**
- [[catalyst-format]] — 催化剂格式（事件、时间窗口、方向、跟踪指标）
- [[bull-bear-divergence]] — 市场共识梳理与预期差识别
- [[observable-indicators]] — 上游前瞻指标与验证信号

---

## 适用的通用约定

全部 5 个 conventions 适用于所有模块：

- [[data-sourcing]] — 数据来源优先级与标注
- [[data-timeliness]] — 时效性要求与过期提示
- [[uncertainty-labeling]] — 不确定性标注规范
- [[web-search-priority]] — 联网检索优先原则
- [[observable-indicators]] — 可观测指标绑定
