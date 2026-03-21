---
type: knowledge
domain: data-quality
applies-to:
  - research-report
  - company-due-diligence
  - company-one-pager
  - theme-stock-picking
  - industry-research
summary: 涉及市场、财务、宏观数据时，必须先联网检索，不得直接依赖训练记忆。
related:
  - "[[data-timeliness]]"
  - "[[data-sourcing]]"
---

## 联网搜索优先

### 规则

涉及公司财务、市场数据、宏观经济指标时，**必须先联网检索，不得直接依赖训练记忆**。

### 数据可信度层级

1. **联网检索结果**（最优先）— 附来源和日期
2. **训练记忆中有明确出处的数据** — 注明来源和数据年份
3. **基于有依据逻辑的估测** — 必须注明【估测】及推导依据
4. **无依据内容** — 直接回答"无相关依据的数据"，不作推断

### 冲突处理

多个来源数据冲突时，列出冲突情况，不擅自选择其中一个作为"正确答案"。

### 搜索工具约定

- 中文搜索：`mcp__WebSearch__bailian_web_search`
- 英文搜索：内置 `WebSearch`
- 网页读取：`mcp__web-reader__webReader`

### 提取自

- 全局 CLAUDE.md — 数据可信度层级、搜索行为规范
- 模块 01 prompt — "结合联网搜索补充必要信息"
- 模块 02 prompt — "联网搜索雪球、巨潮资讯补充竞争对手信息"
- 模块 03 prompt — "请联网搜索补充以下信息"
- 模块 04 prompt — "请联网搜索该公司最新券商研报和盈利预测"
- 模块 05 prompt — "请联网搜索雪球、财经评论区等平台"
- 模块 06 prompt — "请联网搜索以下内容"
