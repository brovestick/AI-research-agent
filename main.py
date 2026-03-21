from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import config
from utils.annual_report_downloader import scan_local_annual_reports
from utils.excel_writer import create_valuation_template
from utils.state_manager import (
    atomic_write_json,
    atomic_write_text,
    init_run_state,
    load_run_state,
    run_dir,
    save_run_state,
)
from utils.user_data_parser import load_user_data_file, merge_user_data


def _log(level: str, msg: str) -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{now}] [{level}] {msg}")


def _find_user_data_file(company_dir: Path) -> Path | None:
    """优先 xlsx，其次 csv。"""
    for suffix in (".xlsx", ".csv"):
        p = company_dir / f"user_data{suffix}"
        if p.exists():
            return p
    return None


def _preflight_company(company_dir: Path) -> None:
    """校验公司目录结构。"""
    user_data_file = _find_user_data_file(company_dir)
    if user_data_file is None:
        raise RuntimeError(f"必填文件缺失: {company_dir}/user_data.xlsx (或 .csv)")

    fin_dir = company_dir / "financial_data"
    if not fin_dir.exists() or not list(fin_dir.glob("*.xlsx")) + list(fin_dir.glob("*.csv")):
        raise RuntimeError(f"financial_data/ 目录不存在或为空: {fin_dir}")

    processed_dir = company_dir / "processed"
    if not processed_dir.exists():
        _log("WARN", f"processed/ 目录不存在: {processed_dir}，请先执行 /登记材料")

    br_dir = processed_dir / "broker_reports"
    if not br_dir.exists() or not list(br_dir.glob("*.md")):
        _log("WARN", "processed/broker_reports/ 为空，模块 01/02 将缺少券商研报输入")


def _load_module(module_id: str):
    spec = config.MODULE_SPECS[module_id]
    module_path = config.BASE_DIR / "modules" / spec["file"]
    mod_spec = importlib.util.spec_from_file_location(f"{spec['slug']}_{module_id}", module_path)
    if mod_spec is None or mod_spec.loader is None:
        raise RuntimeError(f"模块加载失败: {module_path}")
    module = importlib.util.module_from_spec(mod_spec)
    mod_spec.loader.exec_module(module)
    return module


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "company"


def _pick_latest_year(report_paths: dict[int, list[Path]]) -> int:
    if not report_paths:
        raise RuntimeError("未找到可用年报文件。")
    return max(report_paths.keys())


def _ensure_annual_reports(company_dir: Path) -> dict[int, list[Path]]:
    annual_dir = company_dir / "processed" / "annual_reports"
    annual_dir.mkdir(parents=True, exist_ok=True)
    reports = scan_local_annual_reports(str(annual_dir))
    if not reports:
        raise RuntimeError(
            f"未在 {annual_dir} 中找到任何年报文件（MD）。"
            "请先执行 /登记材料 处理原始年报。"
        )
    _log("INFO", f"检测到本地年报: {', '.join(str(y) for y in sorted(reports))}")
    return reports


def _module_paths(run_id: str, module_id: str) -> dict[str, Path]:
    spec = config.MODULE_SPECS[module_id]
    base = run_dir(run_id)
    stem = spec["slug"]
    return {
        "prompt": base / f"{stem}.prompt.md",
        "answer": base / f"{stem}.answer.md",
        "output": base / f"{stem}.md",
        "meta": base / f"{stem}.meta.json",
        "apply_meta": base / f"{stem}.apply_meta.json",
    }


def _assemble_report(state: dict[str, Any]) -> str:
    company = state["company"]
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        f"# {company} 投资研究报告",
        f"生成时间：{generated_at}",
        "",
        "---",
        "",
    ]

    for module_id in config.MODULE_ORDER:
        section = state["sections"].get(module_id)
        if not section:
            continue
        lines.append(f"## {section['title']}")
        lines.append("")
        # 优先从文件路径读取，兼容旧格式的 markdown 字段
        if "path" in section:
            content = Path(section["path"]).read_text(encoding="utf-8").strip()
        else:
            content = section.get("markdown", "").strip()
        lines.append(content)
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("*本报告由 AI 辅助生成，仅供参考，不构成投资建议。*")
    lines.append("")
    return "\n".join(lines)


def _next_action_hint(run_id: str, module_id: str) -> str | None:
    next_module = config.next_module_id(module_id)
    if next_module is None:
        return f"python main.py native finalize --run-id {run_id}"
    if module_id == "03":
        return None
    return f"python main.py native build --run-id {run_id} --module {next_module}"


def native_init(args: argparse.Namespace) -> int:
    company_dir = Path(args.company_dir).resolve()
    _preflight_company(company_dir)

    report_paths = _ensure_annual_reports(company_dir)
    latest_year = _pick_latest_year(report_paths)

    user_data_file = _find_user_data_file(company_dir)
    if user_data_file is None:
        raise RuntimeError("user_data.xlsx (或 .csv) 缺失")
    file_raw = load_user_data_file(user_data_file)
    company = file_raw.get("company", "").strip()
    code = file_raw.get("code", "").strip()
    if not company or not code:
        raise RuntimeError("user_data 必须包含 company 和 code 字段")

    user_data = merge_user_data(cli_args={}, file_path=user_data_file)

    processed_dir = company_dir / "processed"
    financial_data_dir = company_dir / "financial_data"

    state = init_run_state(
        company=company,
        code=code,
        latest_year=latest_year,
        annual_report_paths={year: [str(p) for p in paths] for year, paths in report_paths.items()},
        user_data=user_data,
        company_dir=str(company_dir),
        processed_dir=str(processed_dir),
        financial_data_dir=str(financial_data_dir),
    )

    if user_data:
        fields = ", ".join(sorted(user_data.keys()))
        _log("INFO", f"用户数据已加载: {user_data_file} ({fields})")

    _log("INFO", "Native 初始化完成")
    print(f"RUN_ID={state['run_id']}")
    print("NEXT_COMMAND=python main.py native build --run-id {run_id} --module 01".format(run_id=state["run_id"]))
    return 0


def native_build(args: argparse.Namespace) -> int:
    state = load_run_state(args.run_id)
    module_id = args.module

    if module_id not in config.MODULE_SPECS:
        raise RuntimeError(f"未知模块: {module_id}")
    expected = state.get("next_module")
    if expected and module_id != expected:
        raise RuntimeError(f"当前应执行模块 {expected}，不能直接构建模块 {module_id}。")
    if state.get("approval_required"):
        raise RuntimeError(
            "财务检查点未解锁。仅当用户精确回复 `approve` 后，才能继续后续模块。"
        )

    module = _load_module(module_id)
    result = module.prepare(state["context"], state)

    paths = _module_paths(args.run_id, module_id)
    atomic_write_text(paths["prompt"], str(result["prompt"]).strip() + "\n")
    atomic_write_json(paths["meta"], result.get("meta", {}))

    state["current_module"] = module_id
    state["status"] = "awaiting_answer"
    state["next_module"] = module_id
    state["artifacts"][f"{module_id}_prompt_path"] = str(paths["prompt"])
    state["artifacts"][f"{module_id}_answer_path"] = str(paths["answer"])
    state["artifacts"][f"{module_id}_meta_path"] = str(paths["meta"])
    save_run_state(state)

    print(f"RUN_ID={args.run_id}")
    print(f"MODULE={module_id}")
    print(f"PROMPT_PATH={paths['prompt']}")
    print(f"ANSWER_PATH={paths['answer']}")
    print(f"SKILL_NAME={config.MODULE_SPECS[module_id]['skill_name']}")
    return 0


def native_apply(args: argparse.Namespace) -> int:
    state = load_run_state(args.run_id)
    module_id = args.module
    if state.get("current_module") != module_id:
        raise RuntimeError(f"当前待应用模块不是 {module_id}。当前状态: {state.get('current_module')}")

    answer_path = Path(args.answer_file)
    if not answer_path.exists():
        raise RuntimeError(f"回答文件不存在: {answer_path}")
    answer_text = answer_path.read_text(encoding="utf-8").strip()
    if not answer_text:
        raise RuntimeError(f"回答文件为空: {answer_path}")

    module = _load_module(module_id)
    result = module.apply(state["context"], state, answer_text)

    for key, value in (result.get("context_updates") or {}).items():
        state["context"][key] = value

    paths = _module_paths(args.run_id, module_id)
    spec = config.MODULE_SPECS[module_id]
    section = {
        "title": spec["section_title"],
        "path": str(paths["output"]),
    }
    state["sections"][module_id] = section

    atomic_write_text(paths["output"], result["markdown"] + "\n")
    atomic_write_json(paths["apply_meta"], result.get("meta", {}))
    state["artifacts"][f"{module_id}_output_path"] = str(paths["output"])
    state["artifacts"][f"{module_id}_answer_path"] = str(answer_path)

    review = result.get("review_content")
    if review:
        review_path = run_dir(args.run_id) / "financial_review.md"
        atomic_write_text(review_path, str(review).strip() + "\n")
        state["artifacts"]["financial_review_path"] = str(review_path)

    if module_id == "03":
        state["pending_review"] = "financial_review"
        state["approval_required"] = True
        state["status"] = "awaiting_approval"
        state["current_module"] = "03"
        state["next_module"] = "04"
    else:
        next_module = config.next_module_id(module_id)
        state["pending_review"] = None
        state["approval_required"] = False
        state["status"] = "applied"
        state["current_module"] = module_id
        state["next_module"] = next_module

    save_run_state(state)

    # 知识节点校验 warnings
    warnings = (result.get("meta") or {}).get("warnings", [])
    if warnings:
        print(f"[WARN] 模块{module_id} 知识节点校验：")
        for w in warnings:
            print(f"  - {w}")

    print(f"RUN_ID={args.run_id}")
    print(f"MODULE={module_id}")
    if module_id == "03":
        print(f"FINANCIAL_REVIEW_PATH={state['artifacts']['financial_review_path']}")
        print("WAITING_FOR=approve")
    else:
        hint = _next_action_hint(args.run_id, module_id)
        if hint:
            print(f"NEXT_COMMAND={hint}")
    return 0


def native_approve(args: argparse.Namespace) -> int:
    state = load_run_state(args.run_id)
    if args.value != config.APPROVAL_TOKEN:
        raise RuntimeError("仅接受精确输入 `approve`。其他任何回复均不会放行。")
    if state.get("pending_review") != args.checkpoint or not state.get("approval_required"):
        raise RuntimeError("当前没有可审批的财务检查点。")

    approved = state.get("approved_checkpoints") or []
    if args.checkpoint not in approved:
        approved.append(args.checkpoint)

    state["approved_checkpoints"] = approved
    state["pending_review"] = None
    state["approval_required"] = False
    state["status"] = "approved"
    state["next_module"] = "04"
    save_run_state(state)

    print(f"RUN_ID={args.run_id}")
    print("APPROVED=financial_review")
    print(f"NEXT_COMMAND=python main.py native build --run-id {args.run_id} --module 04")
    return 0


def native_finalize(args: argparse.Namespace) -> int:
    state = load_run_state(args.run_id)
    if state.get("approval_required"):
        raise RuntimeError("存在未完成的审批检查点，无法 finalize。")

    missing = [module_id for module_id in config.MODULE_ORDER if module_id not in state["sections"]]
    if missing:
        raise RuntimeError(f"仍有模块未完成: {', '.join(missing)}")

    report_text = _assemble_report(state)
    company_dir = Path(state["context"]["company_dir"])
    report_path = company_dir / "report.md"
    atomic_write_text(report_path, report_text)
    state["artifacts"]["report_path"] = str(report_path)

    excel_path = company_dir / "估值模板.xlsx"
    create_valuation_template(
        company=state["company"],
        output_path=str(excel_path),
        financials=state["context"].get("financials", {}),
    )
    state["artifacts"]["valuation_excel_path"] = str(excel_path)
    state["status"] = "completed"
    save_run_state(state)

    context_path = run_dir(args.run_id) / "context.final.json"
    atomic_write_text(context_path, json.dumps(state["context"], ensure_ascii=False, indent=2))
    print(f"REPORT_PATH={report_path}")
    print(f"EXCEL_PATH={excel_path}")
    return 0


def native_init_company(args: argparse.Namespace) -> int:
    """创建公司目录骨架和模板 user_data.xlsx。"""
    name = args.name  # 格式: 688102_斯瑞新材
    company_dir = config.COMPANIES_DIR / name
    if company_dir.exists():
        raise RuntimeError(f"公司目录已存在: {company_dir}")

    for sub in [
        "raw/annual_reports", "raw/broker_reports", "raw/announcements", "raw/IR",
        "processed/annual_reports", "processed/broker_reports", "processed/announcements", "processed/IR",
        "financial_data",
    ]:
        (company_dir / sub).mkdir(parents=True, exist_ok=True)

    import pandas as pd

    xlsx_path = company_dir / "user_data.xlsx"
    fields = ["company", "code", "price", "shares", "industry_type", "materials", "comps", "consensus", "material_prices"]
    df = pd.DataFrame({"field": fields, "value": [""] * len(fields)})
    df.to_excel(xlsx_path, index=False)

    _log("INFO", f"公司目录已创建: {company_dir}")
    print(f"COMPANY_DIR={company_dir}")
    print(f"请编辑 {xlsx_path} 填入 company 和 code")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="A股个股投研 Native 工作流")
    subparsers = parser.add_subparsers(dest="command", required=True)

    native = subparsers.add_parser("native", help="Native workflow commands")
    native_sub = native.add_subparsers(dest="native_command", required=True)

    init_company_cmd = native_sub.add_parser("init-company", help="创建公司目录骨架")
    init_company_cmd.add_argument("name", help="公司目录名（如 688102_斯瑞新材）")
    init_company_cmd.set_defaults(func=native_init_company)

    init_cmd = native_sub.add_parser("init", help="初始化一个研究运行")
    init_cmd.add_argument("--company-dir", required=True, help="公司目录路径（如 companies/688102_斯瑞新材）")
    init_cmd.set_defaults(func=native_init)

    build_cmd = native_sub.add_parser("build", help="生成模块 Prompt")
    build_cmd.add_argument("--run-id", required=True)
    build_cmd.add_argument("--module", required=True, choices=config.MODULE_ORDER)
    build_cmd.set_defaults(func=native_build)

    apply_cmd = native_sub.add_parser("apply", help="应用模块回答并更新状态")
    apply_cmd.add_argument("--run-id", required=True)
    apply_cmd.add_argument("--module", required=True, choices=config.MODULE_ORDER)
    apply_cmd.add_argument("--answer-file", required=True)
    apply_cmd.set_defaults(func=native_apply)

    approve_cmd = native_sub.add_parser("approve", help="解锁财务检查点")
    approve_cmd.add_argument("--run-id", required=True)
    approve_cmd.add_argument("--checkpoint", required=True)
    approve_cmd.add_argument("--value", required=True)
    approve_cmd.set_defaults(func=native_approve)

    finalize_cmd = native_sub.add_parser("finalize", help="生成最终研报和估值模板")
    finalize_cmd.add_argument("--run-id", required=True)
    finalize_cmd.set_defaults(func=native_finalize)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:
        _log("ERROR", str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
