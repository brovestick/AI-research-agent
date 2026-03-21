---
name: company-one-pager
description: "为指定上市公司生成一份一页纸投研决策备忘录。触发条件：用户输入公司名称（或股票代码）并要求生成一页纸、投研报告、公司简报等。"
---

# Company One-Pager — 入口

## 准备工作

1. 读取 `output_format.md`，了解角色定义与完整输出格式要求
2. 读取 `retrieval_strategy.md`，了解各 Section 的检索查询模板和工具说明
3. 从用户输入中确认：公司名称、股票代码（如有）

---

## 执行流程（严格串行）

按以下顺序依次完成5个 Section，每个 Section 完成"检索 → 分析 → 输出"后再进入下一个。

各 Section 的具体查询语句见 `retrieval_strategy.md`，输出格式见 `output_format.md`。

**Section 1** → 公司近况（2个查询）

**Section 2** → 核心投资逻辑（5个查询）

**Section 3** → 未来事件与核心跟踪指标（3个查询）

**Section 4** → 业务拆分（4个查询）

**Section 5** → 财务与估值快照（先运行 `fetch_financials.py`，再执行4-6个查询）

---

## 最终整合

所有 Section 完成后，按 `output_format.md` 的格式整合输出完整报告，报告顶部注明生成时间和数据截止日期。

---

## 辅助脚本

`fetch_financials.py`（需与本文件在同一目录）：
```bash
python fetch_financials.py {股票代码}         # 输出 JSON，供 Section 5 读取
python fetch_financials.py {股票代码} --format table  # 输出可读表格，用于调试
```
