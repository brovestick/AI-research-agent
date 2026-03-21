---
name: research-agent-orchestrator
description: Run the native A-share research workflow end-to-end. Trigger when the user says "开始研究", "研究XX公司", "generate a report", or "continue a paused run".
---

# Research Agent Orchestrator

Use this skill to drive the native workflow. The Python code handles files and state. You handle analysis by reading rendered prompts and writing answer files.

## 知识加载协议

### Wikilink 解析规则

prompt 和 MOC 中的 `[[node-name]]` 引用，按以下路径查找对应文件：
- `skills/_knowledge/frameworks/node-name.md`
- `skills/_knowledge/conventions/node-name.md`

### Session 级全局定向

每个 Session 开始（或恢复中断任务）时，主 context 读取 MOC 建立全局视图：
```
skills/_moc/research-report.md
```
MOC 提供 6 模块构成、知识节点映射、依赖关系的全局地图。子进程模块（01-02）不读 MOC（保持精简）。

### Module 级知识加载

每个模块执行前，Agent 按该模块 SKILL.md 中「知识加载」section 列出的节点文件逐一读取。节点内的 `related` wikilinks 可按需跟进（可选，不强制递归）。

### Conventions 处理

5 个 convention 节点的核心规则已嵌入全局 CLAUDE.md（数据可信度层级、标注方式、搜索优先级）。不要求每个模块强制读取 convention 节点——CLAUDE.md 覆盖基础规范，knowledge convention 节点作为深度参考按需读取。

---

## Start a new run

The user must specify a company directory under `companies/`. The `user_data.xlsx` (or `.csv`) inside that directory provides `company` and `code`.

```bash
python main.py native init --company-dir "companies/{code}_{name}"
```

Then run:
`python main.py native build --run-id {run_id} --module 01`

Read the command output to get `PROMPT_PATH` and `ANSWER_PATH`.

## 模块执行策略

模块 01 和 02 使用 Agent 子进程执行（隔离 context，释放 prompt 占用）：
- 调用 Agent 工具，subagent_type="general-purpose"
- prompt 中包含：run_id、PROMPT_PATH、ANSWER_PATH、apply/build 命令、写作风格和溯源要求
- 子进程内部完成：读 prompt → 联网搜索 → 写回答 → apply → build 下一模块
- 子进程返回后，主 context 只获得一条完成摘要

模块 03 在主 context 直接执行（需要展示 financial_review.md 并等用户 approve）。

模块 04、05、06 在主 context 直接执行（prompt 较轻，无需隔离）。

### 子进程模块（01、02）

从 `build` 输出中获取 `PROMPT_PATH` 和 `ANSWER_PATH`，然后调用 Agent 工具：

```
Agent(
  subagent_type="general-purpose",
  prompt="你是投研分析师助理。请完成模块 {module_id} 的分析任务。
    run_id: {run_id}
    步骤：
    1. 按以下顺序读取知识节点文件（Read 工具）：
       {knowledge_file_list}
       （具体文件列表见该模块 SKILL.md 的「知识加载」section）
    2. Read prompt 文件：{PROMPT_PATH}
    3. 理解 prompt 中的任务要求，结合已读取的框架完成分析。用 mcp__WebSearch__bailian_web_search 联网搜索补充信息
    4. 撰写 Markdown 回答，用 cat > \"{ANSWER_PATH}\" << 'ENDOFFILE' ... ENDOFFILE 一次写入
    5. wc -c \"{ANSWER_PATH}\" 确认字节数
    6. 执行：python main.py native apply --run-id {run_id} --module {module_id} --answer-file {ANSWER_PATH}
    7. 执行：python main.py native build --run-id {run_id} --module {next_module_id}
    写作要求：数据驱动，中文，所有数据引用标注【来源：文件名，页码/表格】。
    完成后返回：模块核心结论摘要（3-5句话）+ apply 和 build 是否成功。"
)
```

### 主 context 模块（03、04、05、06）

1. 按该模块 SKILL.md 的「知识加载」section，逐一读取知识节点文件
2. 读取 `build` 输出中的 `PROMPT_PATH`
3. Read prompt 文件，结合已读取的框架理解任务
4. 撰写 Markdown 回答，按 CLAUDE.md 写入规则写入 `ANSWER_PATH`
5. 执行 Skill 末尾写死的 `apply` 命令
6. 执行 Skill 末尾写死的下一条 `build` 命令（模块③除外）

Do not infer the next module from memory. Always follow the module skill's final commands.

## Pause / resume

State is stored in `output/.runs/{run_id}/run_state.json`.
If the conversation is interrupted, resume by reading that file and continuing with the next required command.
