"""Shared FastAPI heuristics.

Endpoint detection is syntactic: a function is treated as an HTTP endpoint
when decorated with a call whose attribute is an HTTP verb (`@app.get(...)`,
`@router.post(...)`, any receiver name). This can over-match unrelated
decorators named after HTTP verbs; document such cases and exclude them
locally rather than weakening the heuristic. WebSocket endpoints are out of
scope (no response-model concept).
"""

from __future__ import annotations

import ast

HTTP_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "trace",
    "api_route",
}

EndpointFunction = ast.FunctionDef | ast.AsyncFunctionDef


def route_decorator(func: EndpointFunction) -> ast.Call | None:
    for decorator in func.decorator_list:
        if (
            isinstance(decorator, ast.Call)
            and isinstance(decorator.func, ast.Attribute)
            and decorator.func.attr in HTTP_METHODS
        ):
            return decorator
    return None


def endpoint_functions(tree: ast.AST) -> list[tuple[EndpointFunction, ast.Call]]:
    endpoints: list[tuple[EndpointFunction, ast.Call]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decorator = route_decorator(node)
            if decorator is not None:
                endpoints.append((node, decorator))
    return endpoints
