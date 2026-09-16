"""ASP003: no module mocking; tests get real dependency seams.

Patching import paths couples a test to module internals, whether via
`unittest.mock.patch`, `mocker.patch`, or `monkeypatch.setattr`. Inject the
dependency through an explicit seam instead. Ruff's TID251 can ban the
imports themselves; this rule catches the call sites. Ports
`no-module-mocking`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import dotted_name

CODE = "ASP003"
MESSAGE = (
    f"{CODE} module mocking; inject the dependency through a real seam "
    "instead of patching import paths"
)

MONKEYPATCH_METHODS = {"setattr", "delattr", "setitem", "delitem"}


def _imported_patch_names(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in {
            "unittest.mock",
            "mock",
        }:
            for alias in node.names:
                if alias.name == "patch":
                    names.add(alias.asname or alias.name)
    return names


def _is_patch_call(func: ast.expr, patch_names: set[str]) -> bool:
    if isinstance(func, ast.Name):
        return func.id in patch_names
    name = dotted_name(func)
    if name is None:
        return False
    root = name.split(".", maxsplit=1)[0]
    if root in patch_names:
        return True
    return ".patch" in name and root in {"mock", "unittest", "mocker"}


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    patch_names = _imported_patch_names(context.tree)
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call):
            continue
        if _is_patch_call(node.func, patch_names):
            yield node.lineno, node.col_offset, MESSAGE
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in MONKEYPATCH_METHODS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "monkeypatch"
        ):
            yield node.lineno, node.col_offset, MESSAGE
