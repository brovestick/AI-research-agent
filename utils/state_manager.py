from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

import config


def new_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")


def run_dir(run_id: str) -> Path:
    path = config.RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_path(run_id: str) -> Path:
    return run_dir(run_id) / "run_state.json"


def atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))


def load_run_state(run_id: str) -> dict[str, Any]:
    path = state_path(run_id)
    if not path.exists():
        raise RuntimeError(f"运行状态不存在: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def save_run_state(state: dict[str, Any]) -> Path:
    run_id = str(state["run_id"])
    path = state_path(run_id)
    atomic_write_json(path, state)
    return path


def init_run_state(
    company: str,
    code: str,
    latest_year: int,
    annual_report_paths: dict[int, list[str]],
    user_data: dict[str, Any] | None = None,
    company_dir: str = "",
    processed_dir: str = "",
    financial_data_dir: str = "",
) -> dict[str, Any]:
    run_id = new_run_id()
    industry_type = "growth"
    if user_data and "industry_type" in user_data:
        industry_type = user_data["industry_type"]

    state = {
        "run_id": run_id,
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "company": company,
        "code": code,
        "latest_year": latest_year,
        "current_module": None,
        "next_module": "01",
        "status": "initialized",
        "pending_review": None,
        "approval_required": False,
        "approved_checkpoints": [],
        "context": {
            "company": company,
            "code": code,
            "latest_year": latest_year,
            "annual_report_paths": annual_report_paths,
            "company_dir": company_dir,
            "processed_dir": processed_dir,
            "financial_data_dir": financial_data_dir,
            "output_dir": str(config.OUTPUT_DIR),
            "run_id": run_id,
            "industry_type": industry_type,
            "financials": {
                "structured": {},
                "qualitative": {},
                "source": {},
            },
            "warnings": [],
            "user_data": user_data or {},
        },
        "sections": {},
        "artifacts": {},
    }
    save_run_state(state)
    return state
