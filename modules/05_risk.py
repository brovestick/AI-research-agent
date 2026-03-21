from __future__ import annotations

from utils.annual_report_downloader import read_annual_report
from utils.prompt_loader import render_prompt


def prepare(context: dict, run_state: dict) -> dict:
    del run_state
    latest_year = int(context["latest_year"])
    annual_report_paths = {int(k): v for k, v in context.get("annual_report_paths", {}).items()}
    paths = annual_report_paths.get(latest_year, [])
    risk_section_text = read_annual_report(
        paths,
        keywords=["风险因素", "面临的风险", "可能面对的风险", "风险提示"],
        max_chars=5000,
    )

    prompt = render_prompt(
        "05",
        {
            "company": context["company"],
            "code": context["code"],
            "risk_section_text": risk_section_text,
        },
    )
    return {
        "prompt": prompt,
        "meta": {"module": "05_risk", "latest_year": latest_year},
    }


_VALIDATION_CHECKS = [
    {
        "node": "observable-indicators",
        "any_of": ["可观测预警", "预警信号", "若看到"],
    },
    {
        "node": "bull-bear-divergence",
        "any_of": ["预期差", "多头", "空头", "估值回调"],
    },
]


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    del context, run_state
    from utils.answer_validator import validate_answer

    warnings = validate_answer(answer_text, _VALIDATION_CHECKS)
    return {
        "markdown": answer_text,
        "context_updates": {},
        "meta": {"module": "05_risk", "warnings": warnings},
    }
