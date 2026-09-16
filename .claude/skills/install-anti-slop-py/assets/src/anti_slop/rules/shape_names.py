"""ASP007: no `shape` in symbol names.

`UserShape` describes structure instead of naming the domain concept that
owns it. A straight port of `no-shape-in-symbol-names`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context

CODE = "ASP007"
MESSAGE = f"{CODE} symbol name contains 'shape'; name the owning domain concept instead"


def _flagged(name: str) -> bool:
    return "shape" in name.lower()


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if _flagged(node.name):
                yield node.lineno, node.col_offset, MESSAGE
        elif isinstance(node, ast.arg):
            if _flagged(node.arg):
                yield node.lineno, node.col_offset, MESSAGE
        elif (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and _flagged(node.id)
        ):
            yield node.lineno, node.col_offset, MESSAGE
