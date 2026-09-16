"""ASF001: every endpoint declares a typed response contract.

An endpoint without a return annotation (and without `response_model` in the
decorator), or annotated `Any`/`dict`, publishes an API whose shape lives
only in the implementation. Annotate the return with a model; FastAPI uses
it for serialization, validation, and the OpenAPI schema.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.fastapi.common import endpoint_functions
from anti_slop.rules.common import dotted_name, is_any

CODE = "ASF001"
MESSAGE = (
    f"{CODE} endpoint without a typed response contract; annotate the "
    "return with a model or set response_model"
)


def _is_dict_annotation(annotation: ast.expr) -> bool:
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    name = dotted_name(target)
    return name is not None and name.split(".")[-1] in {"dict", "Dict"}


def _lacks_contract(returns: ast.expr | None) -> bool:
    if returns is None:
        return True
    return is_any(returns) or _is_dict_annotation(returns)


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for func, decorator in endpoint_functions(context.tree):
        has_response_model = any(
            keyword.arg == "response_model" for keyword in decorator.keywords
        )
        if not has_response_model and _lacks_contract(func.returns):
            yield func.lineno, func.col_offset, MESSAGE
