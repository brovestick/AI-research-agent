from __future__ import annotations

from pathlib import Path

import config
from utils.annual_report_downloader import read_annual_report
from utils.pdf_reader import merge_texts
from utils.prompt_loader import render_prompt


def prepare(context: dict, run_state: dict) -> dict:
    del run_state
    latest_year = int(context["latest_year"])
    annual_report_paths = {int(k): v for k, v in context.get("annual_report_paths", {}).items()}
    industry_type = context.get("industry_type", "growth")

    paths = annual_report_paths.get(latest_year, [])
    annual_report_text = read_annual_report(
        paths,
        keywords=["主营业务", "经营模式", "核心竞争力", "客户", "供应商", "产品"],
        max_chars=config.PDF_MAX_CHARS_PER_FILE,
    )

    company_reports_text = merge_texts(
        directory=str(Path(context["processed_dir"]) / "broker_reports"),
        max_chars=6000,
        per_file_chars=config.PDF_MAX_CHARS_PER_FILE,
    )
    industry_reports_text = ""  # 行业研报不再单独分类，已合并到 broker_reports

    prospectus_text = merge_texts(
        directory=str(Path(context["processed_dir"]) / "announcements"),
        max_chars=6000,
        per_file_chars=config.PDF_MAX_CHARS_PER_FILE,
    )

    cyclical_addendum = ""
    if industry_type == "cyclical":
        cyclical_addendum = (
            "\n\n补充要求：若公司属于周期属性，请在“三、定价机制”部分额外说明当前周期阶段"
            "（上行 / 顶部 / 下行 / 底部）对公司定价能力与加工费稳定性的影响。"
        )

    prompt = render_prompt(
        "02",
        {
            "company": context["company"],
            "code": context["code"],
            "annual_report_text": annual_report_text,
            "company_reports_text": company_reports_text,
            "industry_reports_text": industry_reports_text,
            "prospectus_text": prospectus_text,
            "cyclical_addendum": cyclical_addendum,
        },
    )
    return {
        "prompt": prompt,
        "meta": {
            "module": "02_business",
            "industry_type": industry_type,
            "cyclical_additional_question": industry_type == "cyclical",
        },
    }


_VALIDATION_CHECKS = [
    {
        "node": "product-line-breakdown",
        "any_of": ["营收占比", "收入占比", "收入结构"],
    },
    {
        "node": "competitive-landscape",
        "any_of": ["市占率", "竞争格局", "竞争地位", "龙头", "跟随者"],
    },
    {
        "node": "pricing-power",
        "any_of": ["定价", "提价", "加工费"],
    },
    {
        "node": "value-chain-bargaining",
        "any_of": ["议价", "客户集中", "前五大"],
    },
    {
        "node": "supply-demand-elasticity",
        "any_of": ["供给弹性", "需求弹性", "供需"],
    },
]


def apply(context: dict, run_state: dict, answer_text: str) -> dict:
    del context, run_state
    from utils.answer_validator import validate_answer

    warnings = validate_answer(answer_text, _VALIDATION_CHECKS)
    return {
        "markdown": answer_text,
        "context_updates": {},
        "meta": {"module": "02_business", "warnings": warnings},
    }
