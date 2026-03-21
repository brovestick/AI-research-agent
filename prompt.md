# E2E 测试问题记录

> 测试日期：2026-03-18
> 测试标的：振江股份（603507）
> run_id: 20260318_140437_271158（/撰写报告）、20260318_130454_818879（首轮测试）

---

## 已修复的问题

### 1. `_parse_industry_type` 解析器误判

- **现象**：Agent 运用 `[[cyclical-vs-growth]]` 知识节点后，输出"周期性逻辑当前更主导"等自然语言，旧解析器只做 `str.find("周期性行业")` 精确匹配，两边都匹配不到时 fallback 为 `"growth"`，导致周期股被错误标记
- **修复**：prompt 末尾新增结构化字段要求 `行业判定=cyclical` 或 `行业判定=growth`；解析器优先提取该显式字段，关键词计数作为 fallback
- **涉及文件**：`modules/01_classify.py`、`skills/research-module-01/references/prompt.md`
- **验证**：第二轮 E2E 测试中 `industry_type` 正确输出为 `cyclical`

### 2. 知识节点 `[[...]]` 引用未被读取

- **现象**：`render_prompt()` 保留 `[[xxx]]` 为纯文本，Agent 子进程不会自动读取对应知识节点文件，导致框架要求未被遵循
- **修复**：CLAUDE.md Agent 调用模板和各模块 SKILL.md 中新增显式步骤——识别 `[[xxx]]` 引用，逐一读取 `skills/_knowledge/frameworks/xxx.md` 或 `conventions/xxx.md`
- **设计选择**：不做 inline 展开（保持 arscontexta 按需读取理念）
- **涉及文件**：`CLAUDE.md`、各模块 `SKILL.md`

### 3. 搜索工具名不一致

- **现象**：SKILL.md 和命令文件中使用 `mcp__web-search-prime__web_search_prime`，但该 MCP 账户已欠费；实际可用的是 `mcp__WebSearch__bailian_web_search`
- **修复**：批量替换 4 个文件中的工具名
- **涉及文件**：`skills/research-module-01/SKILL.md`、`skills/research-module-02/SKILL.md`、`skills/research-agent-orchestrator/SKILL.md`、`.claude/commands/撰写报告.md`

---

## 待解决 / 需关注的问题

### 4. DashScope API 欠费

- **现象**：`broker_rpt_extract.py` 调用 `qwen3.5-plus` 时返回 `400 Arrearage`，无法提取券商研报
- **影响**：`/深度研报` 流程无法执行新 PDF 提取，只能使用已有的 processed MD
- **处理**：需登录阿里云 DashScope 控制台充值

### 5. MCP web-search-prime 欠费

- **现象**：`mcp__web-search-prime__web_search_prime` 返回 `余额不足或无可用资源包`
- **影响**：子进程中如果 SKILL.md 还引用旧工具名会搜索失败（已通过问题 3 修复）
- **处理**：已切换到 `mcp__WebSearch__bailian_web_search`；如需恢复 web-search-prime，需充值

### 6. Prompt 财务数据截断

- **现象**：模块 03 的 `build` 阶段，`prepare()` 将多张 XLSX 财务表格拼接注入 prompt 时，数据超出字符上限，在现金流量表 `现金及现金等价物净...` 处被截断，后续的资产负债表详细数据未进入 prompt
- **影响**：模块 03 prompt 中缺少完整的资产负债表明细（存货、应收、应付等），需要通过联网搜索或直接读取 XLSX 文件补充
- **定位**：`modules/03_financial.py` 的 `prepare()` 函数 + `config.py` 中的字符上限配置
- **建议**：考虑提高模块 03 的财务数据字符上限，或改为只注入关键表格（利润表 + 资产负债表摘要），减少冗余列

### 7. 公司名称编码异常

- **现象**：`user_data.csv` 中存储的"振江股份"在 `run_state.json` 中显示为乱码 `___′唤`
- **影响**：prompt 中的公司名称显示为乱码，但不影响分析结果（券商研报和年报内容中有正确公司名）
- **定位**：`user_data.csv` 的编码格式（可能是 GBK 被当作 UTF-8 读取）或 `main.py` 的 CSV 读取逻辑

### 8. 知识节点读取验证缺失

- **现象**：子进程模块（01、02）的知识节点读取依赖 Agent prompt 中的显式指令，无机制验证节点是否被实际读取
- **影响**：如果 Agent 跳过读取步骤，分析质量会下降但不会报错
- **建议**：考虑在 `apply()` 阶段增加轻量检查——验证 answer 中是否包含知识节点要求的关键结构（如 `[[cyclical-vs-growth]]` 要求输出 `行业判定=` 字段）
