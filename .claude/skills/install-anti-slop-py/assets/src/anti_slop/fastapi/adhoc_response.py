"""ASF003: no hand-built JSON responses inside endpoints.

`JSONResponse(content={...})` with a dict literal inside an endpoint skips
validation and the OpenAPI schema, so the shape drifts silently. Return a
model instead. Exception handlers and middleware, where `JSONResponse` is
the sanctioned tool, are not endpoints and stay unflagged.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.fastapi.common import endpoint_functions

CODE = "ASF003"
MESSAGE = (
    f"{CODE} ad hoc dict response; return a response model instead of "
    "hand-built JSON"
)


def _is_json_response(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "JSONResponse"
    if isinstance(node, ast.Attribute):
        return node.attr == "JSONResponse"
    return False


def _dict_literal_content(call: ast.Call) -> bool:
    if call.args and isinstance(call.args[0], ast.Dict):
        return True
    return any(
        keyword.arg == "content" and isinstance(keyword.value, ast.Dict)
        for keyword in call.keywords
    )


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for func, _decorator in endpoint_functions(context.tree):
        for node in ast.walk(func):
            if (
                isinstance(node, ast.Call)
                and _is_json_response(node.func)
                and _dict_literal_content(node)
            ):
                yield node.lineno, node.col_offset, MESSAGE
