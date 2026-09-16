"""ASD005: `TypeAdapter` belongs at module scope.

Pydantic's performance guidance says to build a `TypeAdapter` once and reuse
it; constructing one per call rebuilds the core schema every time. A factory
function that builds adapters on purpose deserves a local exclusion or a
comment saying why.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context

CODE = "ASD005"
MESSAGE = (
    f"{CODE} TypeAdapter instantiated per call; build it once at module "
    "scope and reuse it"
)


def _is_type_adapter_call(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "TypeAdapter"
    if isinstance(node, ast.Attribute):
        return node.attr == "TypeAdapter"
    return False


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    inside_functions: set[int] = set()
    for node in ast.walk(context.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for child in ast.walk(node):
                if child is not node:
                    inside_functions.add(id(child))
    for node in ast.walk(context.tree):
        if (
            isinstance(node, ast.Call)
            and _is_type_adapter_call(node.func)
            and id(node) in inside_functions
        ):
            yield node.lineno, node.col_offset, MESSAGE
