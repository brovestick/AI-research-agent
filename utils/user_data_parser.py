"""解析用户预填数据（CLI 参数 + CSV/XLSX 文件），合并输出标准化 dict。"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _read_csv_with_fallback(path: Path) -> dict[str, str]:
    """读取两列 CSV（field, value），返回 {field: value}。"""
    import csv

    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames is None:
                    continue
                # 兼容列名大小写和空格
                rows: dict[str, str] = {}
                for row in reader:
                    field = (row.get("field") or row.get("Field") or "").strip()
                    value = (row.get("value") or row.get("Value") or "").strip()
                    if field and value:
                        rows[field] = value
                if rows:
                    return rows
        except Exception:
            continue
    return {}


def _read_xlsx(path: Path) -> dict[str, str]:
    """读取两列 XLSX（field, value），返回 {field: value}。"""
    try:
        import pandas as pd

        df = pd.read_excel(path, dtype=str)
        if df.empty or len(df.columns) < 2:
            return {}
        col_field = df.columns[0]
        col_value = df.columns[1]
        rows: dict[str, str] = {}
        for _, row in df.iterrows():
            field = str(row[col_field]).strip()
            value = str(row[col_value]).strip()
            if field and value and field.lower() != "nan" and value.lower() != "nan":
                rows[field] = value
        return rows
    except Exception:
        return {}


def load_user_data_file(path: Path | None) -> dict[str, str]:
    """读取用户数据文件，返回原始 {field: value} 映射。路径为 None 则返回空 dict。"""
    if path is None or not path.exists():
        return {}
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv_with_fallback(path)
    if suffix in (".xlsx", ".xls"):
        return _read_xlsx(path)
    return {}


def parse_comps(raw: str) -> list[dict[str, str]]:
    """'博威合金:601137,楚江新材:002171' → [{'name': '博威合金', 'code': '601137'}, ...]"""
    result: list[dict[str, str]] = []
    for item in raw.split(","):
        item = item.strip()
        if ":" in item:
            name, code = item.split(":", 1)
            result.append({"name": name.strip(), "code": code.strip()})
        elif "：" in item:
            name, code = item.split("：", 1)
            result.append({"name": name.strip(), "code": code.strip()})
    return result


def parse_consensus(raw: str) -> dict[str, float]:
    """'2026E:2.0,2027E:2.55' → {'2026E': 2.0, '2027E': 2.55}"""
    result: dict[str, float] = {}
    for item in raw.split(","):
        item = item.strip()
        sep = ":" if ":" in item else "：" if "：" in item else None
        if sep is None:
            continue
        key, val = item.split(sep, 1)
        try:
            result[key.strip()] = float(val.strip())
        except ValueError:
            continue
    return result


def parse_materials(raw: str) -> list[str]:
    """'铜,铬' → ['铜', '铬']"""
    return [m.strip() for m in raw.split(",") if m.strip()]


def _to_float_or_none(val: str | None) -> float | None:
    if val is None:
        return None
    try:
        return float(val.strip())
    except (ValueError, AttributeError):
        return None


def merge_user_data(
    cli_args: dict[str, Any],
    file_path: Path | None = None,
) -> dict[str, Any] | None:
    """合并文件数据和 CLI 参数，CLI 覆盖文件同名字段。

    返回标准化 dict，如果完全没有数据则返回 None。
    """
    # 先读文件
    file_data = load_user_data_file(file_path)

    # CLI 参数覆盖（只覆盖非 None 的值）
    merged_raw: dict[str, str] = dict(file_data)
    for key, val in cli_args.items():
        if val is not None:
            merged_raw[key] = str(val)

    if not merged_raw:
        return None

    # 标准化输出
    result: dict[str, Any] = {}

    price = _to_float_or_none(merged_raw.get("price"))
    if price is not None:
        result["price"] = price

    shares = _to_float_or_none(merged_raw.get("shares"))
    if shares is not None:
        result["shares"] = shares

    if "industry_type" in merged_raw:
        val = merged_raw["industry_type"].strip().lower()
        if val in ("growth", "cyclical"):
            result["industry_type"] = val

    if "materials" in merged_raw:
        materials = parse_materials(merged_raw["materials"])
        if materials:
            result["materials"] = materials

    if "comps" in merged_raw:
        comps = parse_comps(merged_raw["comps"])
        if comps:
            result["comps"] = comps

    if "consensus" in merged_raw:
        consensus = parse_consensus(merged_raw["consensus"])
        if consensus:
            result["consensus"] = consensus

    if "material_prices" in merged_raw:
        result["material_prices_path"] = merged_raw["material_prices"]

    return result if result else None
