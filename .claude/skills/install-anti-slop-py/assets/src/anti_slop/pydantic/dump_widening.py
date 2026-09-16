"""ASD004: no re-widening a validated model into an untyped dict.

The Pydantic version of `no-widen-then-assert`: the boundary validated the
data into a model, and the code immediately degrades it back to a dict that
travels on without a contract. Two exact syntactic patterns are flagged:

- `f(**model.model_dump())`, also v1's `.dict()`; pass the model, or use
  `Model.model_validate(other)` for model-to-model conversion;
- `x: dict[...] = model.model_dump()`, where the annotation discards the
  model's evidence.

An unannotated `data = model.model_dump()` at a serialization boundary
passes.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import dotted_name

CODE = "ASD004"
MESSAGE = (
    f"{CODE} dumping a validated model into an untyped dict discards "
    "evidence; pass the model, or use model_validate for conversions"
)

DUMP_METHODS = {"model_dump", "dict"}


def _is_dump_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in DUMP_METHODS
    )


def _is_dict_annotation(annotation: ast.expr) -> bool:
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    name = dotted_name(target)
    return name is not None and name.split(".")[-1] in {"dict", "Dict"}


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg is None and _is_dump_call(keyword.value):
                    yield node.lineno, node.col_offset, MESSAGE
        elif isinstance(node, ast.AnnAssign) and (
            node.value is not None
            and _is_dump_call(node.value)
            and _is_dict_annotation(node.annotation)
        ):
            yield node.lineno, node.col_offset, MESSAGE
