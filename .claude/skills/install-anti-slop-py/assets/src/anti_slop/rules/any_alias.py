"""ASP010: no type aliases that conceal `Any`.

`type ExternalValue = Any`, the `TypeAlias` spelling, and a bare
module-level assignment all hide the absence of a contract behind a
domain-sounding name. Ports `no-unknown-type-aliases`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import is_any

CODE = "ASP010"
MESSAGE = (
    f"{CODE} type alias conceals 'Any'; alias a real contract or parse at "
    "the boundary"
)


def _is_type_alias_annotation(annotation: ast.expr) -> bool:
    if isinstance(annotation, ast.Name):
        return annotation.id == "TypeAlias"
    if isinstance(annotation, ast.Attribute):
        return annotation.attr == "TypeAlias"
    return False


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if hasattr(ast, "TypeAlias") and isinstance(node, ast.TypeAlias):
            if is_any(node.value):
                yield node.lineno, node.col_offset, MESSAGE
        elif isinstance(node, ast.AnnAssign) and (
            node.value is not None
            and _is_type_alias_annotation(node.annotation)
            and is_any(node.value)
        ):
            yield node.lineno, node.col_offset, MESSAGE
    if isinstance(context.tree, ast.Module):
        for statement in context.tree.body:
            if isinstance(statement, ast.Assign) and is_any(statement.value):
                yield statement.lineno, statement.col_offset, MESSAGE
