from __future__ import annotations

import re
from pathlib import Path

import config
from utils.annual_report_downloader import read_annual_report
from utils.pdf_reader import merge_texts
from utils.prompt_loader import render_prompt

_EXPLICIT_RE = re.compile(r"行业判定\s*[=:：]\s*(cyclical|growth)")


def _parse_industry_type(result: str) -> str:
    # 优先：LLM 显式填写的结构化字段
    m = _EXPLICIT_RE.search(result)
    if m:
        return m.group(1)

    # Fallback：关键词计数，谁多算谁
    cyc = result.count("周期性行业") + result.count("周期股")
    gro = result.count("成长型行业") + result.count("成长股")
    if cyc != gro:
        return "cyclical" if cyc > gro else "growth"

    return "growth"


def prepare(context: dict, run_state: dict) -> dict:
    del run_state
    latest_year = int(context["latest_year"])
    annual_report_paths = {int(k): v for k, v in context.get("annual_report_paths", {}).items()}

    paths = annual_report_paths.get(latest_year, [])
    annual_report_text = read_annual_report(
        paths,
        keywords=["管理层讨论与分析", "经营情况讨论与分析", "行业情况"],
        max_chars=config.PDF_MAX_CHARS_PER_FILE,
    )

    company_reports_text = merge_texts(
        directory=str(Path(context["processed_dir"]) / "broker_reports"),
        max_chars=8000,
        per_file_chars=config.PDF_MAX_CHARS_PER_FILE,
    )

    prospectus_text = merge_texts(
        directory=str(Path(context["processed_dir"]) / "announcements"),
        max_chars=6000,
        per_file_chars=config.PDF_MAX_CHARS_PER_FILE,
    )

    # 用户预填数据 hint
    user_data = context.get("user_data") or {}
    industry_hint = ""
    if user_data.get("industry_type"):
        label = "成长型行业" if user_data["industry_type"] == "growth" else "周期性行业"
        industry_hint = f"\n> **用户预判**：该公司属于 **{label}**。请验证此判断是否成立，如不同请明确指出。\n"

    prompt = render_prompt(
        "01",
        {
            "company": context["company"],
            "code": context["code"],
            "annual_report_text": annual_report_text,
            "company_reports_text": company_reports_text,
            "prospectus_text": prospectus_text,
            "industry_hint": industry_hint,
        },
    )
    return {
        "prompt": prompt,
        "meta": {"module": "01_classify", "latest_year": latest_year},
    }


_VALIDATION_CHECKS = [
    {
        "node": "cyclical-vs-growth",
        "markers": ["行业判定="],
    },
    {
        "node": "industry-lifecycle",
        "any_of": ["导入期", "成长期", "成熟期", "衰退期"],
    },
]


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    del context, run_state
    from utils.answer_validator import validate_answer

    industry_type = _parse_industry_type(answer_text)
    warnings = validate_answer(answer_text, _VALIDATION_CHECKS)
    return {
        "markdown": answer_text,
        "context_updates": {"industry_type": industry_type},
        "meta": {"module": "01_classify", "industry_type": industry_type, "warnings": warnings},
    }
