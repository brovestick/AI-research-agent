---
type: knowledge
domain: data-quality
applies-to:
  - research-report
  - company-due-diligence
  - company-one-pager
  - theme-stock-picking
  - industry-research
summary: 时间近的数据权重高于时间远的数据；动态数据必须标注时间戳；超12个月须提示过时风险。
related:
  - "[[web-search-priority]]"
  - "[[data-sourcing]]"
  - "[[uncertainty-labeling]]"
---

## 数据时效性纪律

### 核心原则

**时间近 > 时间远。** 联网检索优先查阅发布日期较近的结果，避免因未能及时获取最新信息造成误判。

### 规则

1. 涉及价格、财务数据、市场份额、宏观指标等动态数据时，**必须标注数据时间戳**
2. 若数据超过 12 个月，主动提示"数据可能已过时，建议核实最新数据"
3. 检索结果中有多个时间点的数据时，**优先引用最近的**
4. 所有涉及时效性的内容须标注信息时效，格式：**"截至 {year} 年 X 月"**

### 输出格式要求

该格式要求适用于所有模块和工作流，不仅限于催化剂分析：

> 截至 2025 年 3 月，公司 800G 光模块月出货量约 XX 万只（来源：XXX）

### 当前覆盖差异

- 模块 06 已硬性要求标注"截至 {current_year} 年 X 月"
- 模块 01-05 仅软性提及"近期""最新"，尚未嵌入硬性时间戳格式

### 提取自

- 全局 CLAUDE.md — 时效性要求、数据可信度层级
- 模块 03 prompt — "近 1-2 年价格走势"
- 模块 05 prompt — "最新市场讨论""最新评级"
- 模块 06 prompt — "所有内容须标注信息时效（截至 {current_year} 年 X 月）"
