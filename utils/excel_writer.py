from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from openpyxl.utils import get_column_letter

YELLOW_FILL = PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid")
BOLD = Font(bold=True)


def _auto_width(ws) -> None:
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            v = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(v))
        ws.column_dimensions[col_letter].width = min(max_len + 2, 40)


def create_valuation_template(company: str, output_path: str, financials: dict) -> str:
    wb = Workbook()
    ws1 = wb.active
    ws1.title = "历史数据"
    ws2 = wb.create_sheet("假设参数")
    ws3 = wb.create_sheet("预测输出")
    ws4 = wb.create_sheet("可比估值")

    structured = financials.get("structured", {}) if isinstance(financials, dict) else {}
    history = structured.get("history", {}) if isinstance(structured, dict) else {}

    last_data_row = _build_history_sheet(ws1, history)
    _build_assumption_sheet(ws2, structured)
    _build_projection_sheet(ws3, last_data_row)
    _build_comparable_sheet(ws4, company)

    for ws in [ws1, ws2, ws3, ws4]:
        _auto_width(ws)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return str(out)


def _build_history_sheet(ws, history: dict) -> int:
    """Returns the 1-based row number of the last data row (latest year)."""
    headers = ["年份", "营业收入", "营收增速", "毛利率", "归母净利润", "EPS", "股价（年末）", "PE"]
    ws.append(headers)
    for cell in ws[1]:
        cell.font = BOLD

    years = sorted([y for y in history.keys() if isinstance(y, int)])
    for year in years:
        row = history.get(year, {})
        ws.append(
            [
                year,
                row.get("revenue"),
                row.get("revenue_yoy"),
                row.get("gross_margin"),
                row.get("net_profit"),
                row.get("eps"),
                row.get("price"),
                row.get("pe"),
            ]
        )

    if not years:
        for _ in range(3):
            ws.append([None] * len(headers))

    last_data_row = 1 + max(len(years), 3)

    for _ in range(3):
        ws.append([None] * len(headers))

    return last_data_row


def _build_assumption_sheet(ws, structured: dict) -> None:
    ws.append(["参数", "悲观", "中性", "乐观", "备注"])
    for cell in ws[1]:
        cell.font = BOLD

    products = structured.get("main_products") or ["产品线A", "产品线B"]
    for p in products:
        ws.append([f"{p} 营收增速(%)", None, None, None, "用户填写"])
        ws.append([f"{p} 毛利率(%)", None, None, None, "用户填写"])

    ws.append(["税率假设(%)", None, None, None, "用户填写"])
    ws.append(["费用率假设(%)", None, None, None, "用户填写"])

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=2, max_col=4):
        for cell in row:
            cell.fill = YELLOW_FILL


def _build_projection_sheet(ws, last_data_row: int) -> None:
    ws.append(["指标", "悲观", "中性", "乐观", "说明"])
    for cell in ws[1]:
        cell.font = BOLD

    rows = [
        "未来三年营收（亿元）",
        "未来三年毛利（亿元）",
        "未来三年归母净利润（亿元）",
        "三情景EPS（元）",
        "三情景对应PE",
        "当前股价（可修改）",
        "当前总股本（可修改）",
    ]
    for name in rows:
        ws.append([name, None, None, None, ""])

    r = last_data_row
    ws[2][1].value = f"=IFERROR('历史数据'!B{r}*(1+'假设参数'!C2/100),\"\")"
    ws[2][2].value = f"=IFERROR('历史数据'!B{r}*(1+'假设参数'!D2/100),\"\")"
    ws[2][3].value = f"=IFERROR('历史数据'!B{r}*(1+'假设参数'!E2/100),\"\")"

    ws[4][1].value = "=IFERROR(B4/B8,\"\")"
    ws[4][2].value = "=IFERROR(C4/C8,\"\")"
    ws[4][3].value = "=IFERROR(D4/D8,\"\")"

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=2, max_col=4):
        for cell in row:
            cell.fill = YELLOW_FILL


def _build_comparable_sheet(ws, company: str) -> None:
    ws.append(["公司", "股票代码", "市值（亿元）", "PE（TTM）", "PB", "备注"])
    for cell in ws[1]:
        cell.font = BOLD

    ws.append([company, None, None, None, None, "目标公司"])
    ws.append([None, None, None, None, None, "可比公司1"])
    ws.append([None, None, None, None, None, "可比公司2"])
    ws.append([None, None, None, None, None, "可比公司3"])

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, min_col=2, max_col=5):
        for cell in row:
            cell.fill = YELLOW_FILL
