"""ASD003: no `Any` in model fields.

A field typed `Any`, bare or nested as in `list[Any]`, opts out of the
validation the model exists to provide. Declare a nested model, a TypedDict,
or a concrete type. The generic ASP009 already covers `dict[str, Any]`
fields.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.pydantic.common import model_classes
from anti_slop.rules.common import is_any

CODE = "ASD003"
MESSAGE = (
    f"{CODE} model field typed 'Any' skips validation for that field; "
    "declare a nested model, TypedDict, or concrete type"
)


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for model in model_classes(context.tree):
        for statement in model.body:
            if not isinstance(statement, ast.AnnAssign):
                continue
            if any(is_any(node) for node in ast.walk(statement.annotation)):
                yield statement.lineno, statement.col_offset, MESSAGE
