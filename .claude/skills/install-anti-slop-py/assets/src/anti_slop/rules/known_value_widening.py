"""ASP005: broad dict annotations that discard known keys.

Annotating a literal dict as `dict[str, Handler]` throws away the key set
the literal proves. Rely on inference, mark the binding `Final`, or declare
a `TypedDict`; Python has no `satisfies`. Empty literals pass, since there
the annotation adds evidence instead of destroying it. Ports
`no-known-value-widening`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import dotted_name

CODE = "ASP005"
MESSAGE = (
    f"{CODE} broad dict annotation discards known keys; rely on inference, "
    "Final, or a TypedDict"
)

DICT_BASES = {
    "dict",
    "Dict",
    "typing.Dict",
    "Mapping",
    "typing.Mapping",
    "MutableMapping",
    "typing.MutableMapping",
}


def _is_dict_annotation(annotation: ast.expr) -> bool:
    if not isinstance(annotation, ast.Subscript):
        return False
    base = dotted_name(annotation.value)
    return base is not None and (base in DICT_BASES or base.endswith(".Mapping"))


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.AnnAssign) or node.value is None:
            continue
        if not isinstance(node.value, ast.Dict) or not node.value.keys:
            continue
        literal_keys = all(
            key is not None and isinstance(key, ast.Constant)
            for key in node.value.keys
        )
        if literal_keys and _is_dict_annotation(node.annotation):
            yield node.lineno, node.col_offset, MESSAGE
