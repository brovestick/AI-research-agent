from __future__ import annotations

from datetime import datetime

from utils.prompt_loader import render_prompt


def prepare(context: dict, run_state: dict) -> dict:
    del run_state

    # 用户预填数据 hint
    user_data = context.get("user_data") or {}
    consensus_hint = ""
    if user_data.get("consensus"):
        items = [f"{k}: {v}" for k, v in user_data["consensus"].items()]
        consensus_hint = (
            "\n> **用户提供的一致预期 EPS**（供参考）："
            + "、".join(items)
            + "\n"
        )

    prompt = render_prompt(
        "06",
        {
            "company": context["company"],
            "code": context["code"],
            "current_year": datetime.now().year,
            "consensus_hint": consensus_hint,
        },
    )
    return {
        "prompt": prompt,
        "meta": {"module": "06_catalyst", "current_year": datetime.now().year},
    }


_VALIDATION_CHECKS = [
    {
        "node": "catalyst-format",
        "markers": ["时间窗口"],
        "any_of": ["可观测指标", "可观测"],
    },
    {
        "node": "bull-bear-divergence",
        "any_of": ["分歧", "看多", "看空", "一致预期"],
    },
    {
        "node": "timeliness",
        "regex": r"截至.*\d{4}.*年.*\d{1,2}.*月",
    },
]


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    del context, run_state
    from utils.answer_validator import validate_answer

    warnings = validate_answer(answer_text, _VALIDATION_CHECKS)
    return {
        "markdown": answer_text,
        "context_updates": {},
        "meta": {"module": "06_catalyst", "warnings": warnings},
    }
