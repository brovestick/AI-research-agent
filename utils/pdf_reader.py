from __future__ import annotations

from pathlib import Path
from typing import Iterable

import fitz  # pymupdf


def _limit_text(text: str, max_chars: int) -> tuple[str, bool]:
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def extract_text(pdf_path: str) -> str:
    """提取 PDF 全文，返回字符串"""
    path = Path(pdf_path)
    if not path.exists():
        return ""

    chunks: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            chunks.append(page.get_text("text"))
    return "\n".join(chunks).strip()


def extract_section(pdf_path: str, keywords: list[str], max_chars: int = 8000) -> str:
    """
    根据关键词定位章节，返回该章节文本。
    超过 max_chars 时截断，保留前 max_chars 个字符。
    """
    full_text = extract_text(pdf_path)
    if not full_text:
        return ""

    positions: list[int] = []
    lowered = full_text.lower()
    for keyword in keywords:
        idx = lowered.find(keyword.lower())
        if idx >= 0:
            positions.append(idx)

    if not positions:
        cropped, truncated = _limit_text(full_text, max_chars)
        if truncated:
            return f"{cropped}\n\n以下内容因长度限制已截断"
        return cropped

    sections: list[str] = []
    consumed = 0
    for pos in sorted(set(positions)):
        start = max(0, pos - 300)
        end = min(len(full_text), pos + 3600)
        snippet = full_text[start:end].strip()
        if not snippet:
            continue

        remain = max_chars - consumed
        if remain <= 0:
            break
        limited, truncated = _limit_text(snippet, remain)
        sections.append(limited)
        consumed += len(limited)
        if truncated:
            break

    merged = "\n\n".join(sections).strip() or full_text[:max_chars]
    merged, truncated = _limit_text(merged, max_chars)
    if truncated:
        return f"{merged}\n\n以下内容因长度限制已截断"
    return merged


def merge_pdfs(directory: str, max_chars: int = 8000, per_file_chars: int = 8000) -> str:
    path = Path(directory)
    if not path.exists():
        return ""

    parts: list[str] = []
    total = 0
    hit_limit = False
    for pdf in sorted(path.glob("*.pdf")):
        text = extract_text(str(pdf))
        if not text:
            continue

        text, _ = _limit_text(text, per_file_chars)
        if total + len(text) > max_chars:
            remain = max_chars - total
            if remain <= 0:
                hit_limit = True
                break
            text = text[:remain]
            hit_limit = True

        parts.append(f"=== {pdf.name} ===\n{text}")
        total += len(text)

        if total >= max_chars:
            hit_limit = True
            break

    merged = "\n\n".join(parts).strip()
    if not merged:
        return ""
    if hit_limit:
        return f"{merged}\n\n以下内容因长度限制已截断"
    return merged


def merge_texts(directory: str, max_chars: int = 8000, per_file_chars: int = 8000) -> str:
    """合并目录下所有 MD/TXT 文件，格式同 merge_pdfs。"""
    path = Path(directory)
    if not path.exists():
        return ""

    parts: list[str] = []
    total = 0
    hit_limit = False
    for f in sorted(path.glob("*.md")):
        text = f.read_text(encoding="utf-8").strip()
        if not text:
            continue

        text, _ = _limit_text(text, per_file_chars)
        if total + len(text) > max_chars:
            remain = max_chars - total
            if remain <= 0:
                hit_limit = True
                break
            text = text[:remain]
            hit_limit = True

        parts.append(f"=== {f.name} ===\n{text}")
        total += len(text)

        if total >= max_chars:
            hit_limit = True
            break

    merged = "\n\n".join(parts).strip()
    if not merged:
        return ""
    if hit_limit:
        return f"{merged}\n\n以下内容因长度限制已截断"
    return merged


def list_pdf_files(directory: str) -> list[Path]:
    path = Path(directory)
    if not path.exists():
        return []
    return sorted(path.glob("*.pdf"))


def ensure_total_char_limit(texts: Iterable[str], max_chars: int) -> str:
    merged = "\n\n".join([t for t in texts if t]).strip()
    merged, truncated = _limit_text(merged, max_chars)
    if truncated:
        return f"{merged}\n\n以下内容因长度限制已截断"
    return merged
