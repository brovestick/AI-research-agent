---
type: knowledge
domain: data-quality
applies-to:
  - research-report
  - company-due-diligence
  - company-one-pager
  - theme-stock-picking
  - industry-research
summary: 所有数据引用必须标注来源机构、文件名、页码或表格编号。
related:
  - "[[uncertainty-labeling]]"
  - "[[data-timeliness]]"
  - "[[web-search-priority]]"
---

## 数据溯源标注

### 规则

所有数据引用必须标注来源，格式为 `【来源：文件名，页码/表格】` 或 `（来源：机构名，时间）`。

### 标注层级

| 数据类别 | 标注格式 | 示例 |
|---------|---------|------|
| 一手数据（公司公告、监管文件） | 【来源：文件名，页码】 | 【来源：2024年报，P45 表12】 |
| 专业数据库（LightCounting、Wind） | （来源：机构名，数据期） | （来源：LightCounting，2024Q3） |
| 券商研报 | （来源：券商+报告标题，日期） | （来源：中金《光模块深度》，2024.08） |
| 二手转引（媒体报道、前瞻产业研究院等） | 标注原始出处 + 转引路径 | 原始来源：LightCounting，经前瞻产业研究院转引 |

### 一手 vs 二手区分

一手数据（公司公告、监管文件、交易所数据）优先级高于二手数据（研报引用、媒体报道），引用时须加以区分标注。

### 提取自

- 全局 CLAUDE.md — 数据可信度层级、研究领域数据来源优先级
- 项目 CLAUDE.md — 溯源标记规则
- 模块 01-06 prompt — 各模块均含 "引用来源" 要求
