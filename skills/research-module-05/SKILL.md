---
name: research-module-05
description: Execute module 05 of the native research workflow: risk analysis, then apply the answer and immediately build module 06.
---

# Module 05

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/competitive-landscape.md`
2. `skills/_knowledge/frameworks/bull-bear-divergence.md`
3. `skills/_knowledge/conventions/observable-indicators.md`

Read the rendered prompt from:
`output/.runs/{run_id}/05_risk.prompt.md`

Write the finished Markdown answer to:
`output/.runs/{run_id}/05_risk.answer.md`

执行完毕后，立即执行：
`python main.py native apply --run-id {run_id} --module 05 --answer-file output/.runs/{run_id}/05_risk.answer.md`

完成后执行：
`python main.py native build --run-id {run_id} --module 06`
