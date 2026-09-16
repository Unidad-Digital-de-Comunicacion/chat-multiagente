"""ASF002: no manual request parsing inside endpoints.

`await request.json()`, `.body()`, or `.form()` inside an endpoint re-parses
by hand what a body-model parameter would parse and validate at the
boundary, which is the framework's own "parse, don't validate" seam.
Heuristic: the receiver must be named `request`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.fastapi.common import endpoint_functions

CODE = "ASF002"
MESSAGE = (
    f"{CODE} manual request parsing; declare a body model parameter so "
    "FastAPI parses and validates at the boundary"
)

PARSING_METHODS = {"json", "body", "form", "stream"}


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for func, _decorator in endpoint_functions(context.tree):
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in PARSING_METHODS
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "request"
            ):
                yield node.lineno, node.col_offset, MESSAGE
