---
name: research-module-06
description: Execute module 06 of the native research workflow: catalyst analysis, then apply the answer and finalize the report outputs.
---

# Module 06

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/catalyst-format.md`
2. `skills/_knowledge/frameworks/bull-bear-divergence.md`
3. `skills/_knowledge/conventions/observable-indicators.md`

Read the rendered prompt from:
`output/.runs/{run_id}/06_catalyst.prompt.md`

Write the finished Markdown answer to:
`output/.runs/{run_id}/06_catalyst.answer.md`

执行完毕后，立即执行：
`python main.py native apply --run-id {run_id} --module 06 --answer-file output/.runs/{run_id}/06_catalyst.answer.md`

完成后执行：
`python main.py native finalize --run-id {run_id}`
