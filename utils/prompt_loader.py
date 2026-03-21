from __future__ import annotations

import re
import sys
from pathlib import Path

import config

_PLACEHOLDER_RE = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


class _SafeFormatDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def prompt_template_path(module_id: str) -> Path:
    spec = config.MODULE_SPECS[module_id]
    return config.SKILLS_DIR / spec["skill_name"] / "references" / "prompt.md"


def reference_path(module_id: str, filename: str) -> Path:
    spec = config.MODULE_SPECS[module_id]
    return config.SKILLS_DIR / spec["skill_name"] / "references" / filename


def load_prompt_template(module_id: str) -> str:
    path = prompt_template_path(module_id)
    if not path.exists():
        raise RuntimeError(f"Prompt 模板不存在: {path}")
    return path.read_text(encoding="utf-8")


def load_reference_text(module_id: str, filename: str) -> str:
    path = reference_path(module_id, filename)
    if not path.exists():
        raise RuntimeError(f"Skill 引用文件不存在: {path}")
    return path.read_text(encoding="utf-8").strip()


def render_prompt(module_id: str, variables: dict[str, object]) -> str:
    template = load_prompt_template(module_id)
    rendered = template.format_map(_SafeFormatDict(variables)).strip()

    remaining = set(_PLACEHOLDER_RE.findall(rendered)) - set(variables.keys())
    if remaining:
        print(
            f"[WARN] 模块 {module_id} Prompt 中存在未替换的占位符: {', '.join(sorted(remaining))}",
            file=sys.stderr,
        )
    return rendered
