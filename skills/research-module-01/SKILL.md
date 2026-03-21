---
name: research-module-01
description: Execute module 01 of the native research workflow via Agent subprocess: industry classification for an A-share company.
---

# Module 01 — 子进程自包含指令

本模块通过 Agent 子进程执行。以下是传入子进程 prompt 的完整指令模板。

## 知识加载（执行 prompt 前读取）

1. `skills/_knowledge/frameworks/cyclical-vs-growth.md`
2. `skills/_knowledge/frameworks/industry-lifecycle.md`
3. `skills/_knowledge/frameworks/competitive-landscape.md`

## 子进程 Prompt 模板

```
你是投研分析师助理。请完成模块 01（行业定性与分类）的分析任务。

run_id: {run_id}

## 执行步骤

1. 按以下顺序读取知识节点文件（Read 工具）：
   - skills/_knowledge/frameworks/cyclical-vs-growth.md
   - skills/_knowledge/frameworks/industry-lifecycle.md
   - skills/_knowledge/frameworks/competitive-landscape.md
2. Read prompt 文件：output/.runs/{run_id}/01_classify.prompt.md
3. 仔细阅读 prompt 中的任务要求和参考材料，结合已读取的框架完成分析
4. 用 mcp__WebSearch__bailian_web_search 联网搜索补充行业信息（行业政策、竞争格局、市场规模等）
5. 撰写 Markdown 回答，用以下命令一次写入：
   cat > "output/.runs/{run_id}/01_classify.answer.md" << 'ENDOFFILE'
   （你的回答内容）
   ENDOFFILE
6. 执行 wc -c "output/.runs/{run_id}/01_classify.answer.md" 确认字节数
7. 执行：python main.py native apply --run-id {run_id} --module 01 --answer-file output/.runs/{run_id}/01_classify.answer.md
8. 执行：python main.py native build --run-id {run_id} --module 02

## 写作要求

- 数据驱动，中文撰写，开头表明核心观点
- 所有数据引用标注【来源：文件名，页码/表格】
- 自然的对话式散文，少用列点；只有在对比、清单场景下使用列表

## 完成后返回

返回给主 context 的摘要（3-5 句话）：
- 行业定性核心结论（属于什么行业、处于什么阶段）
- apply 命令是否成功
- build 02 命令是否成功
```

## 主 context 调用方式

在主 context 中，orchestrator 使用 Agent 工具调用本模块：

```
Agent(
  subagent_type="general-purpose",
  description="执行模块01行业分类",
  prompt=（上方模板，填入实际 run_id）
)
```

子进程返回后，主 context 继续执行模块 02（同样用 Agent 子进程）。
