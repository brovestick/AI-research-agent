"""
extract_IR.py
=============
从 .docx 文件中提取表格单元格（文本框）内容，过滤其他内容（标题段落、页眉页脚等）。
专用于提取投资者关系活动记录。

用法：
    # 单文件模式
    python extract_IR.py <input.docx> --output output.md

    # 公司目录模式（逐个处理 raw/IR 下的所有文件）
    python extract_IR.py --company "companies/688102_斯瑞新材"
"""

import argparse
import sys
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path


# Word ML 命名空间
NS = {
    "w":   "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
}

# 目标字段及其输出标签（保持顺序）
TARGET_FIELDS = {
    "投资者关系活动主要内容介绍": "主要内容",
    "日期": "日期",
}

PROCESSED_PREFIX = "(已处理)"


def get_cell_text(cell_elem):
    """提取单个单元格的全部文字（保留换行，忽略空行）。"""
    lines = []
    for para in cell_elem.findall("w:p", NS):
        tokens = []
        for t in para.iter(f"{{{NS['w']}}}t"):
            if t.text:
                tokens.append(t.text)
        text = "".join(tokens).strip()
        if text:
            lines.append(text)
    return "\n\n".join(lines)


def extract_table_cells(docx_path):
    """
    从 docx 中提取目标字段的单元格文本。

    Returns:
        list of dict，每项包含 field_label（输出标签）、content
    """
    docx_path = Path(docx_path)
    if not docx_path.exists():
        raise FileNotFoundError(f"文件不存在：{docx_path}")

    with zipfile.ZipFile(docx_path, "r") as z:
        with z.open("word/document.xml") as f:
            tree = ET.parse(f)

    root = tree.getroot()
    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("无法找到文档 body，文件格式可能不正确。")

    results = []

    for tbl in body.iter(f"{{{NS['w']}}}tbl"):
        for row in tbl.findall("w:tr", NS):
            cells = row.findall("w:tc", NS)
            if len(cells) < 2:
                continue
            left_text = get_cell_text(cells[0]).replace("\n", "").strip()
            # 匹配目标字段
            matched_label = None
            for field, label in TARGET_FIELDS.items():
                if field in left_text:
                    matched_label = label
                    break
            if matched_label is None:
                continue
            content = get_cell_text(cells[1])
            if content:
                results.append({
                    "field_label": matched_label,
                    "content": content,
                })

    return results


def format_output(results):
    """将提取结果格式化为带字段标签的纯文本，适合 LLM 读取。"""
    parts = []
    for item in results:
        parts.append(f"{item['field_label']}：\n{item['content']}")
    return "\n\n".join(parts)


def process_single_file(input_path: Path, output_path: Path, mark_processed: bool = False) -> bool:
    """
    处理单个文件。

    Returns:
        bool: 是否成功处理
    """
    try:
        results = extract_table_cells(str(input_path))
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        return False

    if not results:
        print(f"未找到任何表格内容：{input_path}")
        return False

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(format_output(results), encoding="utf-8")
    print(f"已保存到：{output_path}（共 {len(results)} 个字段）")

    if mark_processed:
        renamed = input_path.parent / f"{PROCESSED_PREFIX}{input_path.name}"
        input_path.rename(renamed)
        print(f"已标记：{input_path.name} -> {renamed.name}")

    return True


def process_company_ir(company_dir: Path) -> dict:
    """
    处理公司目录下所有待处理的 IR 文件。

    规则：
    - 遍历 raw/IR/*.docx
    - 跳过以 (已处理) 开头的文件
    - 逐个处理，前一个完成后再处理下一个
    - 输出到 processed/IR/
    - 处理完后重命名原文件添加 (已处理) 前缀

    Returns:
        dict: {processed: [...], skipped: [...], failed: [...]}
    """
    raw_dir = company_dir / "raw" / "IR"
    output_dir = company_dir / "processed" / "IR"

    if not raw_dir.exists():
        print(f"错误：raw/IR 目录不存在：{raw_dir}")
        return {"processed": [], "skipped": [], "failed": []}

    output_dir.mkdir(parents=True, exist_ok=True)

    result = {"processed": [], "skipped": [], "failed": []}
    docx_files = sorted(raw_dir.glob("*.docx"))

    for docx in docx_files:
        if docx.name.startswith(PROCESSED_PREFIX):
            result["skipped"].append(docx.name)
            print(f"跳过（已处理）: {docx.name}")
            continue

        output_md = output_dir / f"{docx.stem}.md"
        if process_single_file(docx, output_md, mark_processed=True):
            result["processed"].append(docx.name)
        else:
            result["failed"].append(docx.name)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="从 .docx 表格中提取投资者关系活动记录内容。"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("input", nargs="?", help="输入 .docx 文件路径")
    group.add_argument("--company", "-c", help="公司目录路径（批量处理 raw/IR 下的文件）")
    parser.add_argument("--output", "-o", help="输出文件路径（单文件模式）")
    args = parser.parse_args()

    # 公司目录模式
    if args.company:
        company_dir = Path(args.company)
        if not company_dir.exists():
            print(f"错误：公司目录不存在：{company_dir}", file=sys.stderr)
            sys.exit(1)
        result = process_company_ir(company_dir)
        print(f"\n处理完成：{len(result['processed'])} 个文件成功，{len(result['failed'])} 个失败，{len(result['skipped'])} 个已跳过")
        sys.exit(0)

    # 单文件模式
    if not args.input:
        parser.print_help()
        sys.exit(1)

    try:
        results = extract_table_cells(args.input)
    except (FileNotFoundError, ValueError) as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)

    if not results:
        print("未找到任何表格内容。", file=sys.stderr)
        sys.exit(0)

    output_text = format_output(results)

    if args.output:
        Path(args.output).write_text(output_text, encoding="utf-8")
        print(f"已保存到：{args.output}（共 {len(results)} 个字段）")
    else:
        print(output_text)


if __name__ == "__main__":
    main()
