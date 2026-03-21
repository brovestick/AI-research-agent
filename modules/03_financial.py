from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import pandas as pd

import config
from utils.annual_report_downloader import read_annual_report
from utils.prompt_loader import render_prompt

YEAR_PATTERN = re.compile(r"(20\d{2})")
TABLE_FILE_SUFFIXES = (".csv", ".xlsx", ".xls")
QUARTER_HINTS = ("季报", "中报", "半年", "一季", "二季", "三季", "四季", "Q1", "Q2", "Q3", "Q4")


def _read_csv_with_fallback(path: Path) -> pd.DataFrame:
    for enc in ("utf-8-sig", "utf-8", "gbk", "gb18030"):
        try:
            return pd.read_csv(path, encoding=enc)
        except Exception:
            continue
    raise RuntimeError(f"无法读取 CSV: {path}")


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    text = text.replace(",", "").replace("%", "")
    if text in {"--", "-", "N/A", "n/a"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _contains_any(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(k.lower() in lowered for k in keywords)


def _normalize_text(value: Any) -> str:
    return str(value).replace("\u3000", " ").strip()


def _year_priority(label: str) -> int:
    normalized = _normalize_text(label)
    if "年报" in normalized:
        return 3
    if any(h in normalized for h in QUARTER_HINTS):
        return 1
    return 2


def _list_financial_data_files(financial_dir: Path) -> list[Path]:
    files: list[Path] = []
    for suffix in TABLE_FILE_SUFFIXES:
        files.extend(financial_dir.glob(f"*{suffix}"))
    return sorted(path for path in files if path.is_file() and not path.name.startswith("~$"))


def _read_excel_sheet_with_fallback(excel_file: pd.ExcelFile, sheet_name: str) -> pd.DataFrame:
    last_error: Exception | None = None
    for header in (2, 0):
        try:
            return pd.read_excel(excel_file, sheet_name=sheet_name, header=header)
        except Exception as exc:
            last_error = exc
            continue
    if last_error is not None:
        raise RuntimeError(f"无法读取工作表: {sheet_name}") from last_error
    raise RuntimeError(f"无法读取工作表: {sheet_name}")


def _load_tabular_tables(data_files: list[Path]) -> list[tuple[str, pd.DataFrame]]:
    tables: list[tuple[str, pd.DataFrame]] = []
    for data_file in data_files:
        suffix = data_file.suffix.lower()
        if suffix == ".csv":
            try:
                df = _read_csv_with_fallback(data_file)
            except Exception:
                continue
            if not df.empty:
                tables.append((data_file.name, df))
            continue

        try:
            excel_file = pd.ExcelFile(data_file)
        except Exception:
            continue
        for sheet_name in excel_file.sheet_names:
            try:
                df = _read_excel_sheet_with_fallback(excel_file, sheet_name)
            except Exception:
                continue
            if not df.empty:
                tables.append((f"{data_file.name} / {sheet_name}", df))
    return tables


def _extract_year_columns(df: pd.DataFrame) -> list[tuple[int, int, int]]:
    year_columns: list[tuple[int, int, int]] = []
    for idx, col in enumerate(df.columns):
        match = YEAR_PATTERN.search(_normalize_text(col))
        if not match:
            continue
        year_columns.append((idx, int(match.group(1)), _year_priority(str(col))))
    return year_columns


def _metric_matches(metric_name: str, aliases: list[str], excludes: list[str]) -> bool:
    return _contains_any(metric_name, aliases) and not _contains_any(metric_name, excludes)


def _pick_metric_row(
    df: pd.DataFrame,
    year_columns: list[tuple[int, int, int]],
    aliases: list[str],
    excludes: list[str],
    target_years: set[int],
) -> pd.Series | None:
    if df.empty or len(df.columns) < 2:
        return None
    first_col = df.columns[0]
    names = df[first_col].astype(str).map(_normalize_text)
    best_idx: int | None = None
    best_score = -1

    for idx, metric_name in names.items():
        if not _metric_matches(metric_name, aliases, excludes):
            continue
        row = df.loc[idx]
        value_count = 0
        for col_idx, year, _priority in year_columns:
            if year not in target_years:
                continue
            if _to_float(row.iloc[col_idx]) is not None:
                value_count += 1
        if value_count == 0:
            continue

        alias_score = max((len(a) for a in aliases if a.lower() in metric_name.lower()), default=1)
        penalty = 0
        if "同比" in metric_name or "增长率" in metric_name:
            penalty -= 5
        if "其中" in metric_name or "差额" in metric_name:
            penalty -= 3
        score = value_count * 100 + alias_score + penalty
        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx is None:
        return None
    return df.loc[best_idx]


def _set_history_value(
    history: dict[int, dict[str, float | None]],
    selected_priority: dict[tuple[int, str], int],
    year: int,
    metric_key: str,
    value: float,
    priority: int,
) -> None:
    pair = (year, metric_key)
    current_priority = selected_priority.get(pair, -1)
    if priority >= current_priority:
        history[year][metric_key] = value
        selected_priority[pair] = priority


def _extract_structured_from_tables(tables: list[tuple[str, pd.DataFrame]], latest_year: int) -> dict:
    target_years = [latest_year - 2, latest_year - 1, latest_year]
    target_year_set = set(target_years)
    history: dict[int, dict[str, float | None]] = {y: {} for y in target_years}
    selected_priority: dict[tuple[int, str], int] = {}

    metric_rules = {
        "revenue": {"aliases": ["营业收入", "营业总收入", "营收"], "excludes": ["同比", "增长率", "/", "占比"]},
        "net_profit": {
            "aliases": [
                "归母净利润",
                "归属于母公司股东的净利润",
                "归属母公司股东的净利润",
                "归属于母公司所有者的净利润",
                "归属于母公司所有者净利润",
            ],
            "excludes": ["同比", "增长率", "扣除非经常性损益"],
        },
        "gross_margin": {"aliases": ["毛利率", "销售毛利率"], "excludes": ["同比", "增长率"]},
        "revenue_yoy": {"aliases": ["营收增速", "营业收入同比", "营业收入增长率"], "excludes": []},
        "roe": {"aliases": ["roe", "净资产收益率"], "excludes": []},
        "asset_liability_ratio": {"aliases": ["资产负债率"], "excludes": []},
        "inventory_days": {"aliases": ["存货周转天数"], "excludes": []},
        "ar_days": {"aliases": ["应收账款周转天数"], "excludes": []},
        "operating_cashflow": {
            "aliases": ["经营活动产生的现金流量净额", "经营活动产生的现金流量", "经营活动现金流", "经营现金流"],
            "excludes": ["每股", "差额"],
        },
        "eps": {"aliases": ["每股收益-基本", "每股收益", "eps"], "excludes": ["扣除"]},
        "price": {"aliases": ["股价", "收盘价", "年末股价"], "excludes": []},
        "pe": {"aliases": ["pe(ttm)", "市盈率", "pe"], "excludes": []},
    }

    for _table_name, df in tables:
        if df.empty:
            continue

        year_columns = _extract_year_columns(df)

        if year_columns and len(df.columns) >= 2:
            for metric_key, rule in metric_rules.items():
                row = _pick_metric_row(
                    df=df,
                    year_columns=year_columns,
                    aliases=rule["aliases"],
                    excludes=rule["excludes"],
                    target_years=target_year_set,
                )
                if row is None:
                    continue
                for col_idx, year, priority in year_columns:
                    if year not in target_year_set:
                        continue
                    val = _to_float(row.iloc[col_idx])
                    if val is None:
                        continue
                    _set_history_value(history, selected_priority, year, metric_key, val, priority)

        year_col = None
        metric_col = None
        value_col = None
        for idx, col in enumerate(df.columns):
            lower = _normalize_text(col).lower()
            if year_col is None and ("年" in lower or "year" in lower):
                year_col = idx
            if metric_col is None and ("指标" in lower or "项目" in lower or "metric" in lower):
                metric_col = idx
            if value_col is None and ("值" in lower or "value" in lower or "数值" in lower):
                value_col = idx

        if year_col is not None and metric_col is not None and value_col is not None:
            for _, row in df.iterrows():
                year_match = YEAR_PATTERN.search(_normalize_text(row.iloc[year_col]))
                if not year_match:
                    continue
                year = int(year_match.group(1))
                if year not in target_year_set:
                    continue
                metric_name = _normalize_text(row.iloc[metric_col])
                val = _to_float(row.iloc[value_col])
                if val is None:
                    continue
                for metric_key, rule in metric_rules.items():
                    if _metric_matches(metric_name, rule["aliases"], rule["excludes"]):
                        _set_history_value(history, selected_priority, year, metric_key, val, priority=2)
                        break

    revenue_latest = history.get(latest_year, {}).get("revenue")
    net_profit_latest = history.get(latest_year, {}).get("net_profit")
    gross_margin_latest = history.get(latest_year, {}).get("gross_margin")

    revenue_cagr_3y = None
    old_revenue = history.get(latest_year - 2, {}).get("revenue")
    if isinstance(revenue_latest, (int, float)) and isinstance(old_revenue, (int, float)) and old_revenue > 0:
        revenue_cagr_3y = (math.pow(revenue_latest / old_revenue, 1 / 2) - 1) * 100

    return {
        "history": history,
        "revenue_latest": revenue_latest,
        "net_profit_latest": net_profit_latest,
        "revenue_cagr_3y": revenue_cagr_3y,
        "gross_margin_latest": gross_margin_latest,
    }


def _trim_columns_to_recent_years(df: pd.DataFrame, latest_year: int, keep_years: int = 3) -> pd.DataFrame:
    """只保留指标名列 + 近 keep_years 年的年份列，减少 prompt 字符量。"""
    target_years = set(range(latest_year - keep_years + 1, latest_year + 1))
    # 也保留最近的季报（latest_year + 未来预测年份不保留）
    keep_indices = []
    for idx, col in enumerate(df.columns):
        match = YEAR_PATTERN.search(_normalize_text(col))
        if match:
            year = int(match.group(1))
            if year in target_years:
                keep_indices.append(idx)
        else:
            # 非年份列（指标名、分类等）一律保留
            keep_indices.append(idx)
    if not keep_indices:
        return df
    return df.iloc[:, keep_indices]


def _tabular_summary(
    tables: list[tuple[str, pd.DataFrame]],
    max_chars: int = 20000,
    latest_year: int | None = None,
) -> str:
    blocks: list[str] = []
    total = 0
    for table_name, df in tables:
        if latest_year is not None:
            df = _trim_columns_to_recent_years(df, latest_year)
        part = f"=== {table_name} ===\n{df.head(40).to_string(index=False)}"
        if total + len(part) > max_chars:
            remain = max_chars - total
            if remain <= 0:
                break
            blocks.append(part[:remain])
            blocks.append("\n以下内容因长度限制已截断")
            break
        blocks.append(part)
        total += len(part)
    return "\n\n".join(blocks)


def _extract_qualitative_from_result(text: str) -> dict:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    capacity = [line for line in lines if "产能利用率" in line][:5]
    product_mix = [
        line for line in lines if ("占比" in line or "毛利" in line) and ("产品" in line or "业务" in line)
    ][:8]
    second_curve = [line for line in lines if "第二增长曲线" in line or "增长曲线" in line][:3]

    products = re.findall(r"([\u4e00-\u9fa5A-Za-z0-9]{2,20}(?:产品|业务|材料|组件))", text)
    dedup_products: list[str] = []
    for product in products:
        if product not in dedup_products:
            dedup_products.append(product)
        if len(dedup_products) >= 6:
            break

    return {
        "capacity_utilization_notes": capacity,
        "product_mix_notes": product_mix,
        "second_growth_curve_notes": second_curve,
        "main_products": dedup_products,
    }


def _review_content(financials: dict, markdown: str, data_source: str) -> str:
    structured = financials.get("structured", {})
    qualitative = financials.get("qualitative", {})
    lines = [
        "# Financial Review",
        "",
        f"数据源：{data_source}",
        "",
        "## 结构化财务数据",
        f"- 最新年营收：{structured.get('revenue_latest', '待核实')}",
        f"- 最新年归母净利润：{structured.get('net_profit_latest', '待核实')}",
        f"- 最新年毛利率：{structured.get('gross_margin_latest', '待核实')}",
        f"- 近三年营收复合增速：{structured.get('revenue_cagr_3y', '待核实')}",
        "",
        "## 叙述性要点",
        f"- 主要产品线：{', '.join(qualitative.get('main_products', [])) or '待核实'}",
        f"- 产能利用率线索：{' | '.join(qualitative.get('capacity_utilization_notes', [])) or '待核实'}",
        f"- 分产品线索：{' | '.join(qualitative.get('product_mix_notes', [])) or '待核实'}",
        f"- 第二增长曲线：{' | '.join(qualitative.get('second_growth_curve_notes', [])) or '待核实'}",
        "",
        "## 模块原始输出",
        "",
        markdown.strip(),
        "",
        "仅当用户精确回复 `approve` 时，才能继续模块04。",
    ]
    return "\n".join(lines).strip()


def _normalize_history_keys(structured: dict) -> dict:
    history = structured.get("history", {})
    normalized: dict[int, dict[str, Any]] = {}
    for key, value in history.items():
        try:
            normalized[int(key)] = value
        except Exception:
            continue
    structured["history"] = normalized
    return structured


def prepare(context: dict, run_state: dict) -> dict:
    del run_state
    latest_year = int(context["latest_year"])
    data_files = _list_financial_data_files(Path(context["financial_data_dir"]))
    annual_report_paths = {int(k): v for k, v in context.get("annual_report_paths", {}).items()}

    source_map: dict[str, str] = {}
    tables = _load_tabular_tables(data_files)
    if tables:
        financial_data_text = _tabular_summary(tables, max_chars=config.PDF_MAX_CHARS_TOTAL, latest_year=latest_year)
        data_source = "财务表格（CSV/XLSX）"
        structured = _extract_structured_from_tables(tables, latest_year)
        source_map["structured"] = "财务表格（CSV/XLSX）"
    else:
        parts: list[str] = []
        for year in [latest_year, latest_year - 1, latest_year - 2]:
            paths = annual_report_paths.get(year, [])
            if not paths:
                continue
            section_text = read_annual_report(
                paths,
                keywords=["财务报表", "利润表", "资产负债表", "现金流量表", "分产品", "分业务"],
                max_chars=6000,
            )
            if section_text:
                parts.append(f"=== {year}年 ===\n{section_text}")
        financial_data_text = "\n\n".join(parts)
        data_source = "年报PDF"
        structured = {
            "history": {latest_year - 2: {}, latest_year - 1: {}, latest_year: {}},
            "revenue_latest": None,
            "net_profit_latest": None,
            "revenue_cagr_3y": None,
            "gross_margin_latest": None,
        }
        source_map["structured"] = "年报PDF"

    # 用户预填数据 hint
    user_data = context.get("user_data") or {}
    materials_hint = ""
    material_prices_text = ""
    if user_data.get("materials"):
        mat_list = "、".join(user_data["materials"])
        materials_hint = f"\n> **用户提供的主要原材料**：{mat_list}。请重点搜索上述原材料的近期价格走势。\n"
    if user_data.get("material_prices_path"):
        mp_path = Path(user_data["material_prices_path"])
        if not mp_path.is_absolute():
            mp_path = Path(context["company_dir"]) / mp_path
        if mp_path.exists():
            try:
                if mp_path.suffix.lower() == ".csv":
                    mp_df = pd.read_csv(mp_path, encoding="utf-8-sig")
                else:
                    mp_df = pd.read_excel(mp_path)
                material_prices_text = (
                    "\n> **用户提供的原材料价格数据**（无需再联网搜索原材料价格走势）：\n\n"
                    + mp_df.head(60).to_string(index=False)
                    + "\n"
                )
            except Exception:
                pass

    prompt = render_prompt(
        "03",
        {
            "company": context["company"],
            "code": context["code"],
            "data_source": data_source,
            "financial_data_text": financial_data_text,
            "year": latest_year,
            "year-1": latest_year - 1,
            "year-2": latest_year - 2,
            "materials_hint": materials_hint,
            "material_prices_text": material_prices_text,
        },
    )
    return {
        "prompt": prompt,
        "meta": {
            "module": "03_financial",
            "data_source": data_source,
            "data_files": [path.name for path in data_files],
            "prepared_structured": structured,
            "source_map": source_map,
        },
    }


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    module_meta = run_state.get("artifacts", {})
    prepared_meta_path = module_meta.get("03_meta_path")
    data_source = "未知"
    prepared_structured = {
        "history": {},
        "revenue_latest": None,
        "net_profit_latest": None,
        "revenue_cagr_3y": None,
        "gross_margin_latest": None,
    }
    source_map: dict[str, str] = {}

    if prepared_meta_path and Path(prepared_meta_path).exists():
        prepared_meta = json.loads(Path(prepared_meta_path).read_text(encoding="utf-8"))
        data_source = prepared_meta.get("data_source", data_source)
        prepared_structured = prepared_meta.get("prepared_structured", prepared_structured)
        source_map = prepared_meta.get("source_map", source_map)

    prepared_structured = _normalize_history_keys(prepared_structured)

    qualitative = _extract_qualitative_from_result(answer_text)
    prepared_structured["main_products"] = qualitative.get("main_products", [])

    # 完整 financials 仅用于生成 financial_review，不写入 context
    full_financials = {
        "structured": prepared_structured,
        "qualitative": qualitative,
        "source": {**source_map, "qualitative": "LLM(年报+联网)"},
        "revenue_latest": prepared_structured.get("revenue_latest"),
        "net_profit_latest": prepared_structured.get("net_profit_latest"),
        "revenue_cagr_3y": prepared_structured.get("revenue_cagr_3y"),
        "gross_margin_latest": prepared_structured.get("gross_margin_latest"),
        "main_products": qualitative.get("main_products", []),
    }

    # 写入 context 的精简版：不含 qualitative（已存入 financial_review.md）
    financials_for_context = {
        "structured": prepared_structured,
        "source": {**source_map, "qualitative": "LLM(年报+联网)"},
        "revenue_latest": prepared_structured.get("revenue_latest"),
        "net_profit_latest": prepared_structured.get("net_profit_latest"),
        "revenue_cagr_3y": prepared_structured.get("revenue_cagr_3y"),
        "gross_margin_latest": prepared_structured.get("gross_margin_latest"),
        "main_products": qualitative.get("main_products", []),
    }

    from utils.answer_validator import validate_answer

    validation_checks = [
        {
            "node": "financial-metrics-table",
            "any_of": ["营业收入", "毛利率", "ROE", "净利率"],
        },
        {
            "node": "product-line-breakdown",
            "any_of": ["分产品", "产品线", "增长曲线"],
        },
    ]
    warnings = validate_answer(answer_text, validation_checks)

    return {
        "markdown": answer_text,
        "context_updates": {"financials": financials_for_context},
        "meta": {"module": "03_financial", "data_source": data_source, "warnings": warnings},
        "review_content": _review_content(full_financials, answer_text, data_source),
    }
