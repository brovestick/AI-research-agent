---
type: knowledge
domain: industry-analysis
applies-to:
  - research-report
  - company-due-diligence
  - company-one-pager
  - theme-stock-picking
  - industry-research
summary: 判断公司属于周期性行业还是成长型行业，决定后续估值方法和分析侧重。
related:
  - "[[industry-lifecycle]]"
  - "[[valuation-assessment]]"
  - "[[supply-demand-elasticity]]"
  - "[[financial-metrics-table]]"
---

## 周期 vs 成长二分判断

### 判断要求

核心判断：公司所在行业是**周期性行业**还是**成长型行业**？

- 若兼具两种属性，说明哪个逻辑当前更主导
- 此判断将贯穿后续全部分析模块

### 下游影响

| 判断结果 | 估值方法 | 分析侧重 | 条件段落 |
|---------|---------|---------|---------|
| 成长型 | PE / PEG | 营收增速、产品渗透率、市场空间 | 无附加段落 |
| 周期性 | PB-ROE | 周期位置、产能利用率、供需拐点 | 注入 cyclical_addendum（模块02）+ cyclical_section（模块04） |

### 周期股附加分析（cyclical_addendum，模块 02）

当判定为周期性行业时，模块 02 prompt 额外追问供需弹性和周期位置。

### 周期前瞻指标分析（cyclical_section，模块 04）

当判定为周期性行业时，模块 04 prompt 额外注入：

> 周期股估值需重点关注"避免买在低 PE 的行业波峰"。请分析：
> - 该行业的核心周期前瞻指标是什么？（例：玻璃/水泥→房地产开工数据；半导体→台积电资本开支）
> - 当前周期处于哪个阶段（上行 / 顶部 / 下行 / 底部）？依据是什么？
> - 推荐用 PB-ROE 框架评估：当前 PB 对应的历史分位数是多少？

### 提取自

- 模块 01 prompt — "核心判断：周期性行业 还是 成长型行业？"及判断依据要求
- 模块 02 — cyclical_addendum 条件注入机制
- 模块 04 — cyclical_section.md 全文
- 模块 05 prompt — "行业周期下行风险（若为周期股，须重点分析）"
