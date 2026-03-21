---
name: research-module-04
description: Execute module 04 of the native research workflow: valuation analysis after financial approval, then apply the answer and immediately build module 05.
---

# Module 04

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/three-scenario-assumption.md`
2. `skills/_knowledge/frameworks/product-line-breakdown.md`
3. `skills/_knowledge/frameworks/valuation-assessment.md`
4. `skills/_knowledge/conventions/observable-indicators.md`

Read the rendered prompt from:
`output/.runs/{run_id}/04_valuation.prompt.md`

Write the finished Markdown answer to:
`output/.runs/{run_id}/04_valuation.answer.md`

执行完毕后，立即执行：
`python main.py native apply --run-id {run_id} --module 04 --answer-file output/.runs/{run_id}/04_valuation.answer.md`

完成后执行：
`python main.py native build --run-id {run_id} --module 05`
