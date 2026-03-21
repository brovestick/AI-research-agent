from __future__ import annotations

import re
from pathlib import Path

YEAR_PATTERN = re.compile(r"(20\d{2})")


def scan_local_annual_reports(annual_report_dir: str) -> dict[int, list[Path]]:
    """
    扫描目录下所有 PDF 和 MD 文件，从文件名中提取年份。
    返回 {年份: [路径列表]}。
    同年有 .md 时只返回 .md 文件；无 .md 才返回 .pdf 文件。
    """
    base = Path(annual_report_dir)
    if not base.exists():
        return {}

    md_by_year: dict[int, list[Path]] = {}
    pdf_by_year: dict[int, list[Path]] = {}

    for f in sorted(base.iterdir()):
        if f.name.startswith("~$") or not f.is_file():
            continue
        suffix = f.suffix.lower()
        if suffix not in (".pdf", ".md"):
            continue
        matches = YEAR_PATTERN.findall(f.name)
        if not matches:
            continue
        year = int(matches[-1])
        if suffix == ".md":
            md_by_year.setdefault(year, []).append(f)
        else:
            pdf_by_year.setdefault(year, []).append(f)

    reports: dict[int, list[Path]] = {}
    all_years = set(md_by_year) | set(pdf_by_year)
    for year in all_years:
        if year in md_by_year:
            reports[year] = md_by_year[year]
        else:
            reports[year] = pdf_by_year[year]

    return reports


def read_annual_report(
    paths: str | list[str],
    keywords: list[str],
    max_chars: int = 8000,
) -> str:
    """
    统一读取年报内容。
    - paths 含 .md → 读取所有 .md 拼接，截断到 max_chars
    - paths 含 .pdf → 调用 extract_section(pdf, keywords, max_chars)
    - 向后兼容：如果传入 str（旧格式单路径），自动包装为 [str]
    """
    if isinstance(paths, str):
        paths = [paths]
    if not paths:
        return ""

    resolved = [Path(p) for p in paths]
    existing = [p for p in resolved if p.exists()]
    if not existing:
        return ""

    md_files = [p for p in existing if p.suffix.lower() == ".md"]
    if md_files:
        parts: list[str] = []
        total = 0
        for md in md_files:
            text = md.read_text(encoding="utf-8").strip()
            if not text:
                continue
            if total + len(text) > max_chars:
                remain = max_chars - total
                if remain > 0:
                    parts.append(text[:remain])
                break
            parts.append(text)
            total += len(text)
        return "\n\n".join(parts)

    from utils.pdf_reader import extract_section

    pdf_file = existing[0]
    return extract_section(str(pdf_file), keywords=keywords, max_chars=max_chars)
