---
name: theme-stock-picking
description: "针对指定投资主题，检索产业链结构、相关上市公司及市场趋势，生成包含主题概览、产业链图谱和30-40家核心标的的选股报告。触发条件：用户输入某一投资主题（如'人形机器人'、'CPO光模块'）并要求选股、梳理产业链或生成主题报告。"
---

# Theme Stock Picking — 入口

## 准备工作

读取以下4个文件，了解完整执行规则：
1. `user_query_format.md` — 将用户输入格式化为标准研究问题
2. `reflection_and_planning.md` — 任务分类规则与4计划生成规则
3. `sub_query_generation.md` — 子查询拆解规则
4. `report_generation.md` — 最终报告的结构、格式硬性要求与写作风格

---

## 执行流程

### 阶段 1：研究准备 [1/3]

1. 将用户输入按 `user_query_format.md` 格式化为标准研究问题
2. 按 `reflection_and_planning.md` 的规则，生成4个计划（JSON格式输出）
3. 按 `sub_query_generation.md` 的规则，为 Plan 1-3 各自拆解1-3个子查询

### 阶段 2：数据与信息检索 [2/3]

**Plan 1、2、3 串行执行**（各自完成所有子查询后进入下一个）：

- 对每个子查询：执行 `web_search`，对最相关的2-3个结果页面执行 `web_fetch` 深入读取
- 检索重点：东方财富、同花顺、雪球、Wind资讯、公司公告

### 阶段 3：整合与报告生成 [3/3]

**Plan 4**：综合 Plan 1-3 的所有检索结果，严格按 `report_generation.md` 的结构与格式要求输出：

1. **主题概览**（1200-1500字）
2. **产业链图谱**（1-3张 Mermaid 流程图）
3. **核心选股表**（30-40家公司）
