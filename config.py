from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMPANIES_DIR = BASE_DIR / "companies"
OUTPUT_DIR = BASE_DIR / "output"
RUNS_DIR = OUTPUT_DIR / ".runs"
SKILLS_DIR = BASE_DIR / "skills"

PDF_MAX_CHARS_PER_FILE = 8000
PDF_MAX_CHARS_TOTAL = 20000
APPROVAL_TOKEN = "approve"

MODULE_ORDER = ["01", "02", "03", "04", "05", "06"]
MODULE_SPECS = {
    "01": {
        "file": "01_classify.py",
        "slug": "01_classify",
        "section_title": "一、行业定性",
        "skill_name": "research-module-01",
    },
    "02": {
        "file": "02_business.py",
        "slug": "02_business",
        "section_title": "二、商业模式分析",
        "skill_name": "research-module-02",
    },
    "03": {
        "file": "03_financial.py",
        "slug": "03_financial",
        "section_title": "三、财务分析",
        "skill_name": "research-module-03",
    },
    "04": {
        "file": "04_valuation.py",
        "slug": "04_valuation",
        "section_title": "四、估值建模",
        "skill_name": "research-module-04",
    },
    "05": {
        "file": "05_risk.py",
        "slug": "05_risk",
        "section_title": "五、风险梳理",
        "skill_name": "research-module-05",
    },
    "06": {
        "file": "06_catalyst.py",
        "slug": "06_catalyst",
        "section_title": "六、催化剂与时间窗口",
        "skill_name": "research-module-06",
    },
}


def next_module_id(module_id: str) -> str | None:
    try:
        idx = MODULE_ORDER.index(module_id)
    except ValueError:
        return None

    if idx + 1 >= len(MODULE_ORDER):
        return None
    return MODULE_ORDER[idx + 1]
