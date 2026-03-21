#!/usr/bin/env python3
"""年报/半年报智能提取 —— 自动定位并仅提取必读章节

用法：
    python3 tools/annrpt_extract.py <pdf_path>

自动识别目录，提取：
  - 第三节 管理层讨论与分析（按子节结构输出，表格内联）
  - 附注定点提取：应收账龄、存货分项、在建工程明细

输出格式：半结构化 Markdown（子节标题 + 清洗文本 + 内联表格）。
附注如需按页补提，可用 pdf_extract.py <pdf> <start> <end>。
"""

import sys
import os
import re
import pdfplumber

# 从同目录导入 pdf_extract 的表格函数
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pdf_extract import extract_tables_with_merge, table_to_markdown


# ─── 中文数字转换 ───────────────────────────────────────────

_CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5,
       '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}


def _cn_to_int(s):
    """中文数字 → 整数（一 ~ 二十）"""
    if len(s) == 1:
        return _CN[s]
    if s[0] == '十':          # 十一, 十二 …
        return 10 + _CN[s[1]]
    if s[-1] == '十':         # 二十
        return _CN[s[0]] * 10
    return _CN[s[0]] * 10 + _CN[s[-1]]  # 二十一 …


# ─── 章节索引 ───────────────────────────────────────────────

_TOC_RE = re.compile(
    r'(第[一二三四五六七八九十]+节)\s+(.+?)\s*[\.…·]{2,}\s*(\d+)'
)


def build_section_index(pdf):
    """从目录页构建章节索引。

    Returns
    -------
    list[(num, label, name, page_1based)] | None
        num   : 章节序号（整数）
        label : 原始标签，如 "第三节"
        name  : 章节名，如 "管理层讨论与分析"
        page  : 起始页码（1-based，已校正偏移）
    """
    entries = []

    for i in range(min(10, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ''
        if '目录' not in text:
            continue
        matches = _TOC_RE.findall(text)
        if len(matches) >= 3:
            for label, name, page_str in matches:
                cn = label[1:-1]  # 去掉 "第" 和 "节"
                num = _cn_to_int(cn)
                entries.append((num, label, name.strip(), int(page_str)))
            break

    if not entries:
        return _fallback_scan(pdf)

    return _validate_offset(pdf, entries)


def _validate_offset(pdf, entries):
    """校验 TOC 页码与物理页是否一致，不一致则计算偏移并修正。"""
    first_num, first_label, _, first_page = entries[0]

    if first_page < 1 or first_page > len(pdf.pages):
        return entries

    text = pdf.pages[first_page - 1].extract_text() or ''
    if first_label in text:
        return entries  # 无偏移

    for delta in range(-5, 6):
        if delta == 0:
            continue
        idx = first_page - 1 + delta
        if 0 <= idx < len(pdf.pages):
            t = pdf.pages[idx].extract_text() or ''
            if first_label in t:
                _info(f"检测到页码偏移 {delta:+d}，已自动修正")
                return [(n, l, nm, p + delta) for n, l, nm, p in entries]

    _warn("无法验证页码偏移，使用 TOC 标注页码")
    return entries


def _fallback_scan(pdf):
    """TOC 解析失败时，全文扫描 '第X节' 标记定位章节。"""
    _warn("TOC 解析失败，回退为全文扫描章节标记")
    sec_re = re.compile(r'^(第[一二三四五六七八九十]+节)\s+(.+)', re.MULTILINE)
    seen = {}

    for i, page in enumerate(pdf.pages):
        text = page.extract_text() or ''
        for m in sec_re.finditer(text):
            label = m.group(1)
            name = m.group(2).strip().split('\n')[0]
            cn = label[1:-1]
            try:
                num = _cn_to_int(cn)
            except (KeyError, IndexError):
                continue
            if num not in seen:
                seen[num] = (num, label, name, i + 1)

    return sorted(seen.values()) if seen else None


# ─── 财务报告子结构定位 ─────────────────────────────────────

def locate_financial_substructure(pdf, start_page, end_page):
    """在财务报告章节内定位主表起止页与附注起始页。

    Returns
    -------
    (tables_start, tables_end, notes_start)  — 均为 1-based 页码
        tables_start : 首个含 "编制单位" 的页（主表起始）
        tables_end   : 附注前一页（主表结束）
        notes_start  : 首个含 "公司基本情况"/"重要会计政策" 的页
    """
    tables_start = None
    notes_start = None

    for i in range(start_page - 1, min(end_page, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ''
        pnum = i + 1

        # 主表起始：首个含 "编制单位" 的页
        if tables_start is None and '编制单位' in text:
            tables_start = pnum

        # 附注起始：主表之后出现 "公司基本情况" 或 "重要会计政策"
        if tables_start and notes_start is None and pnum > tables_start + 3:
            if '公司基本情况' in text:
                notes_start = pnum
            elif '重要会计政策' in text:
                notes_start = pnum

    if tables_start and notes_start:
        return tables_start, notes_start - 1, notes_start
    if tables_start:
        return tables_start, end_page, None
    return None, None, None


# ─── 文本清洗 ─────────────────────────────────────────────

_RE_HEADER = re.compile(r'.+公司\d{4}年(年度|半年度)报告')
_RE_FOOTER = re.compile(r'^\d+\s*/\s*\d+$')
_RE_CHECKBOX = re.compile(r'^[□√☑☐]\s*适用\s+[□√☑☐]\s*不适用\s*$')


def _clean_text(text):
    """过滤页眉、页脚、勾选框等噪声行。"""
    lines = text.split('\n')
    out = []
    for line in lines:
        s = line.strip()
        if _RE_HEADER.match(s):
            continue
        if _RE_FOOTER.match(s):
            continue
        if _RE_CHECKBOX.match(s):
            continue
        out.append(line)
    return '\n'.join(out)


# ─── 子节检测与结构化输出 ─────────────────────────────────

_H1 = re.compile(r'^[一二三四五六七八九十]+、')
_H2 = re.compile(r'^[（(][一二三四五六七八九十]+[）)]')
_H3 = re.compile(r'^\d+、\s')
_SEC_TITLE = re.compile(r'^第[一二三四五六七八九十]+节')


def _detect_heading(line):
    """检测行是否为子节标题，返回 (level, title) 或 None。"""
    s = line.strip()
    if not s or _SEC_TITLE.match(s):
        return None
    if _H1.match(s):
        return (1, s)
    if _H2.match(s):
        return (2, s)
    if _H3.match(s):
        return (3, s)
    return None


def _extract_structured(pdf, start_page, end_page):
    """按子节结构输出第三节，清洗文本 + 内联表格。返回提取字符数。"""
    end_idx = min(end_page, len(pdf.pages))

    # ── Pass 1: 提取清洗文本、识别所有子节标题 ──
    page_data = []   # [(page_0idx, cleaned_text)]
    headings = []    # [(pd_idx, line_idx, title, level)]
    sec_title_pos = None  # (pd_idx, line_idx) — "第X节 ..." 标题行位置

    for pi in range(start_page - 1, end_idx):
        text = pdf.pages[pi].extract_text() or ''
        text = _clean_text(text)
        pd_idx = len(page_data)
        page_data.append((pi, text))

        for li, line in enumerate(text.split('\n')):
            s = line.strip()
            if not s:
                continue
            if _SEC_TITLE.match(s):
                if sec_title_pos is None:
                    sec_title_pos = (pd_idx, li)
                continue
            h = _detect_heading(line)
            if h:
                headings.append((pd_idx, li, h[1], h[0]))

    # 过滤：仅保留节标题之后的子节标题
    if sec_title_pos:
        st_pd, st_li = sec_title_pos
        headings = [(pd, li, t, l) for pd, li, t, l in headings
                    if pd > st_pd or (pd == st_pd and li > st_li)]

    print("# 第三节 管理层讨论与分析\n")
    chars = 0

    # 确定正文起始位置（节标题之后）
    body_pd = sec_title_pos[0] if sec_title_pos else 0
    body_li = sec_title_pos[1] + 1 if sec_title_pos else 0

    if not headings:
        # 未检测到子节结构，从节标题后原样输出
        for pd_i in range(body_pd, len(page_data)):
            _, text = page_data[pd_i]
            lines = text.split('\n')
            if pd_i == body_pd:
                lines = lines[body_li:]
            t = '\n'.join(lines).strip()
            if t:
                print(t)
                print()
                chars += len(t)
        return chars

    # ── 输出首个标题前的文本（从节标题到首个子节标题之间）──
    fh_pd, fh_li = headings[0][0], headings[0][1]
    for pd_i in range(body_pd, fh_pd + 1):
        _, text = page_data[pd_i]
        lines = text.split('\n')
        line_start = body_li if pd_i == body_pd else 0
        line_end = fh_li if pd_i == fh_pd else len(lines)
        pre = '\n'.join(lines[line_start:line_end]).strip()
        if pre:
            print(pre)
            chars += len(pre)

    # ── 逐子节输出文本 + 内联表格 ──
    for hi, (h_pd, h_li, h_title, h_level) in enumerate(headings):
        md = {1: '##', 2: '###', 3: '####'}[h_level]
        print(f"\n{md} {h_title}\n")

        # 确定文本终止位置
        if hi + 1 < len(headings):
            n_pd, n_li = headings[hi + 1][0], headings[hi + 1][1]
        else:
            n_pd, n_li = len(page_data), 0

        # 收集子节文本
        parts = []
        for pd_i in range(h_pd, min(n_pd + 1, len(page_data))):
            _, text = page_data[pd_i]
            lines = text.split('\n')
            line_start = h_li + 1 if pd_i == h_pd else 0
            line_end = (n_li if (pd_i == n_pd and hi + 1 < len(headings))
                        else len(lines))
            parts.append('\n'.join(lines[line_start:line_end]))

        sec_text = '\n'.join(parts).strip()
        if sec_text:
            print(sec_text)
            chars += len(sec_text)

        # 提取该子节页范围内的表格
        h_page = page_data[h_pd][0]
        if hi + 1 < len(headings):
            n_page = page_data[n_pd][0]
            t_pages = ([pdf.pages[pi] for pi in range(h_page, n_page)]
                       if n_page > h_page else [])
        else:
            t_pages = [pdf.pages[pi] for pi in range(h_page, end_idx)]

        if t_pages:
            for tbl in extract_tables_with_merge(t_pages):
                print(f"\n{table_to_markdown(tbl)}\n")

    return chars


# ─── 附注定点搜索 ─────────────────────────────────────────

def _locate_note_table(pdf, notes_start, notes_end, match_fn, label,
                       extra_pages=2):
    """在附注区域搜索特定表格，返回 Markdown 字符串。"""
    end = min(notes_end, len(pdf.pages))
    for i in range(notes_start - 1, end):
        text = pdf.pages[i].extract_text() or ''
        if match_fn(text):
            pages = pdf.pages[i:min(i + 1 + extra_pages, end)]
            tables = extract_tables_with_merge(pages)
            if tables:
                return '\n\n'.join(table_to_markdown(t) for t in tables)
            _warn(f"{label}：关键词在 p{i+1} 找到但未提取到表格")
            return '[未找到]'
    _warn(f"未找到 {label} 表")
    return '[未找到]'


def _find_detail_notes_start(pdf, notes_start, notes_end):
    """定位附注明细起始页（跳过会计政策等前置内容）。

    搜索 "合并财务报表项目注释" / "报表项目注释" 等标记。
    若未找到，返回 notes_start（降级为从附注开头搜索）。
    """
    for i in range(notes_start - 1, min(notes_end, len(pdf.pages))):
        text = pdf.pages[i].extract_text() or ''
        if '报表项目注释' in text or '报表附注' in text:
            _info(f"附注明细起始: p{i+1}")
            return i + 1
    return notes_start


def _match_ar_aging(text):
    """应收账龄分布表匹配。"""
    return '按账龄披露' in text or '账龄分析' in text


def _match_inventory(text):
    """存货分项表匹配（仅匹配附注明细编号，跳过会计政策标题）。"""
    return bool(re.search(r'\d+、\s*存货', text))


def _match_cip(text):
    """在建工程明细表匹配（仅匹配附注明细编号，跳过会计政策标题）。"""
    return bool(re.search(r'\d+、\s*在建工程', text))


# ─── 辅助 ───────────────────────────────────────────────────

def _info(msg):
    print(f"[INFO] {msg}", file=sys.stderr)


def _warn(msg):
    print(f"[WARNING] {msg}", file=sys.stderr)


# ─── 主流程 ─────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    pdf_path = sys.argv[1]

    with pdfplumber.open(pdf_path) as pdf:
        total = len(pdf.pages)
        _info(f"PDF 总页数: {total}")

        # 1. 构建章节索引
        entries = build_section_index(pdf)

        if entries is None:
            _warn("无法解析章节结构，输出全文")
            for i in range(total):
                text = pdf.pages[i].extract_text() or ''
                text = _clean_text(text)
                if text.strip():
                    print(text)
            return

        _info("章节索引:")
        for _, label, name, page in entries:
            _info(f"  {label} {name} → p{page}")

        # 按页码排序，用于计算每节结束页
        by_page = sorted(entries, key=lambda e: e[3])
        idx = {e[0]: e for e in entries}

        def end_page_of(target_num):
            for i, e in enumerate(by_page):
                if e[0] == target_num:
                    return by_page[i + 1][3] - 1 if i + 1 < len(by_page) else total
            return total

        # 查找财务报告章节（不硬编码为第十节，半年报是第八节）
        fin_num = None
        for num, _, name, _ in entries:
            if '财务报告' in name:
                fin_num = num
                break

        total_chars = 0

        # 2. 提取第三节（结构化输出）
        if 3 in idx:
            _, _, n3, s3 = idx[3]
            e3 = end_page_of(3)
            _info(f"第三节 {n3}: p{s3}-{e3}")
            total_chars += _extract_structured(pdf, s3, e3)

        # 3. 附注定点提取
        if fin_num and fin_num in idx:
            _, lbl, nf, sf = idx[fin_num]
            ef = end_page_of(fin_num)
            _, _, ns = locate_financial_substructure(pdf, sf, ef)

            if ns:
                _info(f"附注区域: p{ns}-{ef}")
                # 定位明细起始页（跳过会计政策）
                detail_start = _find_detail_notes_start(pdf, ns, ef)
                print("\n# 附注定点提取\n")

                print("## 应收账龄\n")
                print(_locate_note_table(pdf, detail_start, ef,
                                         _match_ar_aging, '应收账龄'))

                print("\n## 存货分项\n")
                print(_locate_note_table(pdf, detail_start, ef,
                                         _match_inventory, '存货分项'))

                print("\n## 在建工程明细\n")
                print(_locate_note_table(pdf, detail_start, ef,
                                         _match_cip, '在建工程明细'))
            else:
                _warn("未能定位附注区域，跳过附注定点提取")
                print("\n# 附注定点提取\n")
                print("## 应收账龄\n[未找到]\n")
                print("## 存货分项\n[未找到]\n")
                print("## 在建工程明细\n[未找到]\n")

        _info(f"提取完成，共 {total_chars:,} 字符")


if __name__ == "__main__":
    main()
