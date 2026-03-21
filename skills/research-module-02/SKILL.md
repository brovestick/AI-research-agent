---
name: research-module-02
description: Execute module 02 of the native research workflow via Agent subprocess: business model analysis.
---

# Module 02 — 子进程自包含指令

本模块通过 Agent 子进程执行。以下是传入子进程 prompt 的完整指令模板。

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/product-line-breakdown.md`
2. `skills/_knowledge/frameworks/competitive-landscape.md`
3. `skills/_knowledge/frameworks/value-chain-bargaining.md`
4. `skills/_knowledge/frameworks/supply-demand-elasticity.md`
5. `skills/_knowledge/frameworks/pricing-power.md`

## 子进程 Prompt 模板

```
你是投研分析师助理。请完成模块 02（商业模式分析）的分析任务。

run_id: {run_id}

## 执行步骤

1. 按以下顺序读取知识节点文件（Read 工具）：
   - skills/_knowledge/frameworks/product-line-breakdown.md
   - skills/_knowledge/frameworks/competitive-landscape.md
   - skills/_knowledge/frameworks/value-chain-bargaining.md
   - skills/_knowledge/frameworks/supply-demand-elasticity.md
   - skills/_knowledge/frameworks/pricing-power.md
2. Read prompt 文件：output/.runs/{run_id}/02_business.prompt.md
3. 仔细阅读 prompt 中的任务要求和参考材料，结合已读取的框架完成分析
4. 用 mcp__WebSearch__bailian_web_search 联网搜索补充信息（商业模式、竞争优势、产业链位置等）
5. 撰写 Markdown 回答，用以下命令一次写入：
   cat > "output/.runs/{run_id}/02_business.answer.md" << 'ENDOFFILE'
   （你的回答内容）
   ENDOFFILE
6. 执行 wc -c "output/.runs/{run_id}/02_business.answer.md" 确认字节数
7. 执行：python main.py native apply --run-id {run_id} --module 02 --answer-file output/.runs/{run_id}/02_business.answer.md
8. 执行：python main.py native build --run-id {run_id} --module 03

## 写作要求

- 数据驱动，中文撰写，开头表明核心观点
- 所有数据引用标注【来源：文件名，页码/表格】
- 自然的对话式散文，少用列点；只有在对比、清单场景下使用列表

## 完成后返回

返回给主 context 的摘要（3-5 句话）：
- 商业模式核心发现（盈利模式、竞争壁垒、产业链位置）
- apply 命令是否成功
- build 03 命令是否成功
```

## 主 context 调用方式

在主 context 中，orchestrator 使用 Agent 工具调用本模块：

```
Agent(
  subagent_type="general-purpose",
  description="执行模块02商业模式",
  prompt=（上方模板，填入实际 run_id）
)
```

子进程返回后，主 context 继续执行模块 03（在主 context 直接执行，因为需要审批交互）。
