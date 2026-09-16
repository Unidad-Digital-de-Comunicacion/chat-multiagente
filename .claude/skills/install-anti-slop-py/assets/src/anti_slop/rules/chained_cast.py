"""ASP004: chained casts are fabricated evidence.

`cast(User, cast(object, value))` launders a value through the top type,
exactly what `value as object as User` does in TypeScript. Ports
`no-chained-type-assertions`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import is_cast_call

CODE = "ASP004"
MESSAGE = (
    f"{CODE} chained casts fabricate evidence; parse the value or justify a "
    "single cast"
)


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call) or not is_cast_call(node.func):
            continue
        if len(node.args) >= 2:
            value = node.args[1]
            if isinstance(value, ast.Call) and is_cast_call(value.func):
                yield node.lineno, node.col_offset, MESSAGE
