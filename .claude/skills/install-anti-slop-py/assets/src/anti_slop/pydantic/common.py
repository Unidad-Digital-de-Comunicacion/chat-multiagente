"""Shared Pydantic heuristics.

Model detection is syntactic. A class counts as a Pydantic model when a base
name (last dotted segment) is `BaseModel`, `RootModel`, or `BaseSettings`,
or when it inherits, within the same module, from a class already identified
as one. A base visible only through an import alias or another module goes
undetected; report that as a limitation instead of pretending cross-module
inheritance is covered.
"""

from __future__ import annotations

import ast

MODEL_BASE_NAMES = {"BaseModel", "RootModel", "BaseSettings"}


def _base_name(base: ast.expr) -> str | None:
    if isinstance(base, ast.Subscript):
        base = base.value
    if isinstance(base, ast.Name):
        return base.id
    if isinstance(base, ast.Attribute):
        return base.attr
    return None


def model_classes(tree: ast.AST) -> list[ast.ClassDef]:
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    model_names = set(MODEL_BASE_NAMES)
    models: list[ast.ClassDef] = []
    found_ids: set[int] = set()
    changed = True
    while changed:
        changed = False
        for cls in classes:
            if id(cls) in found_ids:
                continue
            base_names = {_base_name(base) for base in cls.bases}
            if base_names & model_names:
                models.append(cls)
                found_ids.add(id(cls))
                model_names.add(cls.name)
                changed = True
    return models
