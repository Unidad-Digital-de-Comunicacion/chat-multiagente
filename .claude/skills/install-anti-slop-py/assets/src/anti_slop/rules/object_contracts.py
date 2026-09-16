"""ASP008: no function contracts typed as bare `object`.

Python's safe top type is `object` (TypeScript's `unknown`), and a contract
built on it makes every caller re-derive the evidence. Ruff's ANN401 owns
the `Any` half; this rule owns `object`. Dunder methods are exempt because
`__eq__(self, other: object)` is the documented signature, and so are
parameters named `cause`, matching the upstream convention. Ports
`no-unknown-parameters` and `no-unknown-returns`.
"""

from __future__ import annotations

from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import function_nodes, is_bare_object

CODE = "ASP008"
PARAMETER_MESSAGE = (
    f"{CODE} parameter typed 'object' hides the real contract; declare the "
    "owner type or parse at the boundary"
)
RETURN_MESSAGE = (
    f"{CODE} return typed 'object' hides the real contract; declare the "
    "owner type"
)

ALLOWED_PARAMETER_NAMES = {"cause"}


def _is_dunder(name: str) -> bool:
    return name.startswith("__") and name.endswith("__")


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for func in function_nodes(context.tree):
        if _is_dunder(func.name):
            continue
        parameters = [
            *func.args.posonlyargs,
            *func.args.args,
            *func.args.kwonlyargs,
        ]
        for parameter in parameters:
            if parameter.arg in ALLOWED_PARAMETER_NAMES:
                continue
            if is_bare_object(parameter.annotation):
                yield parameter.lineno, parameter.col_offset, PARAMETER_MESSAGE
        if is_bare_object(func.returns):
            yield func.lineno, func.col_offset, RETURN_MESSAGE
