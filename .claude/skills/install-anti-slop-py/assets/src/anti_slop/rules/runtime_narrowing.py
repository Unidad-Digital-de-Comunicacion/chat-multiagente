"""ASP002: no ad hoc runtime narrowing.

Scattered `isinstance`, `hasattr`, and `type(x) is` checks re-derive facts
the boundary should have parsed once, with Pydantic or a dataclass
constructor. Pass `--anti-slop-allow-typeguards` and checks inside functions
returning `TypeGuard`/`TypeIs` are permitted, mirroring the upstream
`allowInTypeGuards` option. Ports `no-runtime-typeof`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context

CODE = "ASP002"
MESSAGE = (
    f"{CODE} ad hoc runtime narrowing; parse input at the boundary or move "
    "the check into a TypeGuard/TypeIs function"
)

NARROWING_CALLS = {"isinstance", "hasattr"}
GUARD_RETURNS = {"TypeGuard", "TypeIs"}


def _is_type_guard(func: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    if func.returns is None:
        return False
    for node in ast.walk(func.returns):
        if isinstance(node, ast.Name) and node.id in GUARD_RETURNS:
            return True
        if isinstance(node, ast.Attribute) and node.attr in GUARD_RETURNS:
            return True
    return False


def _guarded_nodes(tree: ast.AST) -> set[int]:
    guarded: set[int] = set()
    for func in ast.walk(tree):
        if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_type_guard(func):
            guarded.update(id(child) for child in ast.walk(func))
    return guarded


def _is_type_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "type"
        and len(node.args) == 1
    )


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    guarded = _guarded_nodes(context.tree) if context.allow_typeguards else set()
    for node in ast.walk(context.tree):
        if id(node) in guarded:
            continue
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in NARROWING_CALLS
        ):
            yield node.lineno, node.col_offset, MESSAGE
        elif isinstance(node, ast.Compare):
            operands = [node.left, *node.comparators]
            if any(_is_type_call(operand) for operand in operands):
                yield node.lineno, node.col_offset, MESSAGE
