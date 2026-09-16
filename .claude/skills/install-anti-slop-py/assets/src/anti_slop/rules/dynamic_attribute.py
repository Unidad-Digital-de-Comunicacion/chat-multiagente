"""ASP006: no dynamic attribute access.

Ruff's B009/B010 reject `getattr(x, "attr")` with a constant name. This rule
rejects the computed-name form, where the type checker loses the contract
entirely. Covers the ground of `no-reflect-get` and `no-reflect-apply`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context

CODE = "ASP006"
MESSAGE = (
    f"{CODE} dynamic attribute access; use typed attribute access, an "
    "explicit registry mapping, or boundary parsing"
)

ATTRIBUTE_BUILTINS = {"getattr", "setattr", "delattr"}


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ATTRIBUTE_BUILTINS
            and len(node.args) >= 2
            and not isinstance(node.args[1], ast.Constant)
        ):
            yield node.lineno, node.col_offset, MESSAGE
