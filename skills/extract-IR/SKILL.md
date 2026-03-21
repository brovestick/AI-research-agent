---
name: extract-IR
description: 提取公司 raw/IR 文件夹下的投资者关系活动记录.docx 文件，输出结构化 Markdown 到 processed/IR/，并标记已处理文件。
---

# /提取 IR 工作流

## 命令格式

```
/提取 IR XX公司
```

其中 `XX 公司` 为公司目录名（如 `688102_斯瑞新材`），位于 `companies/` 目录下。

## 执行步骤

### 1. 确认公司目录

公司目录格式：`companies/{代码}_{简称}/`

必须存在以下结构：
- `companies/{公司}/raw/IR/` - 原始.docx 文件
- `companies/{公司}/processed/IR/` - 输出目录（如不存在会自动创建）

### 2. 扫描待处理文件

遍历 `companies/{公司}/raw/IR/*.docx`，过滤规则：
- 跳过文件名以 `(已处理)` 开头的文件
- 仅处理尚未处理的 `.docx` 文件

### 3. 执行处理命令

```bash
python tools/extract_IR.py --company "companies/{公司}"
```

脚本会逐个处理文件：
1. 读取 `raw/IR/xxx.docx`
2. 提取表格内容（字段：`投资者关系活动主要内容介绍`、`日期`）
3. 输出到 `processed/IR/xxx.md`
4. 将原文件重命名为 `(已处理)xxx.docx`

### 4. 输出结果

处理完成后返回：
- 处理文件数量
- 输出文件列表
- 跳过的文件列表（如有）

## 示例

```bash
# 处理单个公司的所有 IR 文件
python tools/extract_IR.py --company "companies/688102_斯瑞新材"

# 单文件模式（可选）
python tools/extract_IR.py "companies/688102_斯瑞新材/raw/IR/活动记录.docx" \
  --output "companies/688102_斯瑞新材/processed/IR/活动记录.md"
```

## 注意事项

- `.docx` 文件必须包含表格格式的投资者关系活动记录
- 提取的字段：`投资者关系活动主要内容介绍 `、` 日期`
- 如文件中未找到目标表格，输出提示"未找到任何表格内容"
- 已处理的文件会自动添加 `(已处理)` 前缀，避免重复处理
- 多个文件时逐个处理，前一个处理完后再处理下一个
