"""知识节点读取验证：检查模块回答是否包含知识节点要求的关键标记。"""

from __future__ import annotations

import re


def validate_answer(answer: str, checks: list[dict]) -> list[str]:
    """校验 answer 是否包含知识节点要求的关键标记。

    checks 格式::

        [
            {
                "node": "cyclical-vs-growth",        # 知识节点名
                "markers": ["行业判定="],              # 必须全部出现
                "any_of": ["周期性行业", "成长型行业"], # 至少出现其一
                "regex": r"截至.*\\d{4}.*年",          # 可选，正则匹配
            },
            ...
        ]

    返回 warnings 列表（空 = 全部通过）。
    """
    warnings: list[str] = []
    for check in checks:
        node = check.get("node", "unknown")

        # markers: 必须全部出现
        for marker in check.get("markers", []):
            if marker not in answer:
                warnings.append(
                    f"[[{node}]] 未检测到必需标记「{marker}」，该知识节点可能未被读取"
                )

        # any_of: 至少出现其一
        any_of = check.get("any_of", [])
        if any_of and not any(kw in answer for kw in any_of):
            hints = "/".join(any_of)
            warnings.append(
                f"[[{node}]] 未检测到关键标记（{hints}），该知识节点可能未被读取"
            )

        # regex: 正则匹配
        pattern = check.get("regex")
        if pattern and not re.search(pattern, answer):
            warnings.append(
                f"[[{node}]] 未匹配到正则「{pattern}」"
            )

    return warnings
