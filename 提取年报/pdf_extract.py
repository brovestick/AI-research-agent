#!/usr/bin/env python3
"""PDF 提取工具 —— 支持跨页表格自动合并

用法：
    python3 tools/pdf_extract.py <pdf_path> [start_page] [end_page]

页码为 1-based（与 PDF 页码一致）。省略页码则提取全部页。

输出：
    1) 逐页文本（以 --- Page N --- 分隔）
    2) 合并后的表格（Markdown 格式）
"""

import sys
import pdfplumber


def extract_tables_with_merge(pages):
    """从多页中提取表格，自动合并跨页表格。

    合并逻辑：若上一页末尾表格与下一页开头表格列数相同，
    视为同一表格的延续，合并并跳过重复表头行。
    """
    merged_tables = []
    pending = None  # 待定表格（可能还有后续页延续）

    for page in pages:
        page_tables = page.extract_tables()
        if not page_tables:
            # 本页无表格，将待定表格落定
            if pending is not None:
                merged_tables.append(pending)
                pending = None
            continue

        for idx, table in enumerate(page_tables):
            if not table:
                continue

            if idx == 0 and pending is not None:
                # 检查是否为上一页表格的延续
                if len(table[0]) == len(pending[0]):
                    # 判断首行是否为重复表头
                    if table[0] == pending[0]:
                        pending.extend(table[1:])
                    else:
                        pending.extend(table)
                    continue
                else:
                    # 列数不同，非延续，落定上一个
                    merged_tables.append(pending)
                    pending = None

            # 非首个表格或无待定表格时，落定之前的待定并开始新表格
            if pending is not None:
                merged_tables.append(pending)
            pending = list(table)

    # 最后一个待定表格落定
    if pending is not None:
        merged_tables.append(pending)

    return merged_tables


def table_to_markdown(table):
    """将二维列表转为 Markdown 表格字符串。"""
    if not table or len(table) < 1:
        return ""

    def clean(cell):
        if cell is None:
            return ""
        return str(cell).replace("\n", " ").strip()

    lines = []
    # 表头
    header = [clean(c) for c in table[0]]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * len(header)) + " |")
    # 数据行
    for row in table[1:]:
        cells = [clean(c) for c in row]
        # 处理列数不一致的情况
        while len(cells) < len(header):
            cells.append("")
        lines.append("| " + " | ".join(cells[:len(header)]) + " |")

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]
    start = int(sys.argv[2]) - 1 if len(sys.argv) > 2 else 0
    end = int(sys.argv[3]) if len(sys.argv) > 3 else None

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        if end is None:
            end = total
        end = min(end, total)
        pages = pdf.pages[start:end]

        # 1. 提取文本
        print("=" * 60)
        print("TEXT CONTENT")
        print("=" * 60)
        for i, page in enumerate(pages):
            page_num = start + i + 1
            text = page.extract_text()
            if text:
                print(f"\n--- Page {page_num} ---\n")
                print(text)

        # 2. 提取并合并表格
        tables = extract_tables_with_merge(pages)
        if tables:
            print("\n" + "=" * 60)
            print("TABLES (cross-page merged)")
            print("=" * 60)
            for idx, table in enumerate(tables, 1):
                print(f"\n### Table {idx}\n")
                print(table_to_markdown(table))


if __name__ == "__main__":
    main()
