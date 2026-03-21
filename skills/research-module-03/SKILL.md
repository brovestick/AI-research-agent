---
name: research-module-03
description: Execute module 03 of the native research workflow: financial analysis, then stop at the strict approve checkpoint before module 04.
---

# Module 03

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/financial-metrics-table.md`
2. `skills/_knowledge/frameworks/product-line-breakdown.md`

Read the rendered prompt from:
`output/.runs/{run_id}/03_financial.prompt.md`

Write the finished Markdown answer to:
`output/.runs/{run_id}/03_financial.answer.md`

执行完毕后，立即执行：
`python main.py native apply --run-id {run_id} --module 03 --answer-file output/.runs/{run_id}/03_financial.answer.md`

然后向用户展示：
`output/.runs/{run_id}/financial_review.md`

明确提示：只有当用户精确回复 `approve` 时才能继续。

如果用户回复不是精确的 `approve`：
- 不执行任何后续命令
- 重新提示用户输入 `approve`

如果用户精确回复 `approve`：
先执行：
`python main.py native approve --run-id {run_id} --checkpoint financial_review --value approve`

完成后执行：
`python main.py native build --run-id {run_id} --module 04`
