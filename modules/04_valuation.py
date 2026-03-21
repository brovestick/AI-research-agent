from __future__ import annotations

from typing import Any

from utils.prompt_loader import load_reference_text, render_prompt


def _fmt_num(value: Any, ndigits: int = 2) -> str:
    if value is None:
        return "待核实"
    try:
        return f"{float(value):.{ndigits}f}"
    except Exception:
        return str(value)


def prepare(context: dict, run_state: dict) -> dict:
    del run_state
    company = context["company"]
    code = context["code"]
    latest_year = int(context["latest_year"])
    industry_type = context.get("industry_type", "growth")
    financials = context.get("financials", {}) or {}
    structured = financials.get("structured", {}) if isinstance(financials, dict) else {}

    revenue_latest = structured.get("revenue_latest", financials.get("revenue_latest"))
    net_profit_latest = structured.get("net_profit_latest", financials.get("net_profit_latest"))
    revenue_cagr_3y = structured.get("revenue_cagr_3y", financials.get("revenue_cagr_3y"))
    gross_margin_latest = structured.get("gross_margin_latest", financials.get("gross_margin_latest"))
    main_products = structured.get("main_products", financials.get("main_products", []))
    if not isinstance(main_products, list):
        main_products = []

    industry_type_cn = "周期性行业" if industry_type == "cyclical" else "成长型行业"
    valuation_method = "PB" if industry_type == "cyclical" else "PE / PEG"
    cyclical_section = ""
    if industry_type == "cyclical":
        cyclical_section = load_reference_text("04", "cyclical_section.md")

    # 用户预填数据 hint
    user_data = context.get("user_data") or {}

    # 股价 / 股本
    price_shares_hint = ""
    price_shares_instruction = "请先联网查询当前股价和最新股本后再填写 EPS 和 PE。"
    price = user_data.get("price")
    shares = user_data.get("shares")
    if price is not None and shares is not None:
        price_shares_hint = f"\n> **用户提供的市场数据**：当前股价 **{price}** 元，总股本 **{shares}** 亿股。\n"
        price_shares_instruction = "请使用上述用户提供的股价和股本数据计算 EPS 和 PE。"
    elif price is not None:
        price_shares_hint = f"\n> **用户提供的市场数据**：当前股价 **{price}** 元。请联网查询最新股本。\n"
    elif shares is not None:
        price_shares_hint = f"\n> **用户提供的市场数据**：总股本 **{shares}** 亿股。请联网查询当前股价。\n"

    # 一致预期
    consensus_hint = ""
    if user_data.get("consensus"):
        items = [f"{k}: {v}" for k, v in user_data["consensus"].items()]
        consensus_hint = (
            "\n> **用户提供的一致预期 EPS**（作为参考锚点，可微调但不应偏离过大）："
            + "、".join(items)
            + "\n"
        )

    # 可比公司
    comps_hint = ""
    if user_data.get("comps"):
        comp_items = [f"{c['name']}（{c['code']}）" for c in user_data["comps"]]
        comps_hint = "\n> **用户建议的可比公司**：" + "、".join(comp_items) + "。请优先搜索上述公司的估值数据。\n"

    prompt = render_prompt(
        "04",
        {
            "company": company,
            "code": code,
            "industry_type_cn": industry_type_cn,
            "valuation_method": valuation_method,
            "revenue_latest": _fmt_num(revenue_latest),
            "net_profit_latest": _fmt_num(net_profit_latest),
            "revenue_cagr_3y": _fmt_num(revenue_cagr_3y),
            "gross_margin_latest": _fmt_num(gross_margin_latest),
            "main_products": ", ".join(main_products) if main_products else "待核实",
            "year": latest_year,
            "year+1": latest_year + 1,
            "year+2": latest_year + 2,
            "year+3": latest_year + 3,
            "cyclical_section": cyclical_section,
            "price_shares_hint": price_shares_hint,
            "consensus_hint": consensus_hint,
            "price_shares_instruction": price_shares_instruction,
            "comps_hint": comps_hint,
        },
    )
    return {
        "prompt": prompt,
        "meta": {
            "module": "04_valuation",
            "industry_type": industry_type,
            "valuation_method": valuation_method,
        },
    }


_VALIDATION_CHECKS = [
    {
        "node": "three-scenario-assumption",
        "markers": ["乐观", "悲观", "中性"],
    },
    {
        "node": "causal-chain-reasoning",
        "any_of": ["因果链", "传导机制", "关键变量", "⚡"],
    },
    {
        "node": "valuation-assessment",
        "any_of": ["可比公司", "偏贵", "合理", "偏便宜"],
    },
]


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    del context, run_state
    from utils.answer_validator import validate_answer

    warnings = validate_answer(answer_text, _VALIDATION_CHECKS)
    return {
        "markdown": answer_text,
        "context_updates": {},
        "meta": {"module": "04_valuation", "warnings": warnings},
    }
