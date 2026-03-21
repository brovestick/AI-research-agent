---
type: knowledge
domain: data-quality
applies-to:
  - research-report
  - company-due-diligence
  - company-one-pager
  - theme-stock-picking
  - industry-research
summary: 已验证数据直接引用，估测数据标注【估测】并附推导链，无依据数据标注【无相关依据】。
related:
  - "[[data-sourcing]]"
  - "[[data-timeliness]]"
---

## 不确定数据标注

### 三级标注体系

| 数据确定性 | 标注方式 | 要求 |
|-----------|---------|------|
| 已验证数据 | 直接引用，注明来源 | 如：来源：Bloomberg，2024Q3 |
| 估测数据 | **【估测】** 前缀 | 必须附完整推导链，让读者可逐步验证 |
| 无依据数据 | **【无相关依据】** | 不作进一步推断，不使用"大约""约为""估计在"等模糊措辞 |

### 禁止行为

- 编造 PE/PS/EV 等估值倍数
- 编造营收、利润、增速等财务数字
- 在无数据支撑时使用"大约""约为""估计在"等措辞（必须改为【估测】并说明推导依据）
- 将历史数据当作当前数据使用而不注明时间

### 模块级补充

模块 03 prompt 额外要求：不确定的数据标注"待核实"，不要编造数字。

### 提取自

- 全局 CLAUDE.md — 数据标注方式、投资研究禁止行为
- 模块 03 prompt — "不确定的数据请标注'待核实'，不要编造数字"
