"""ASP009: no dictionary contracts with `Any` or `object` values.

`dict[str, Any]` and `Mapping[str, object]` are structure without evidence;
define a `TypedDict`, dataclass, or Pydantic model instead. mypy's
`disallow_any_explicit` catches the `Any` half, Ruff's ANN401 misses it
inside generics, and neither touches the `object` variant. Ports
`no-unsafe-dictionary-type`.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import dotted_name, is_any, is_bare_object

CODE = "ASP009"
MESSAGE = (
    f"{CODE} dictionary contract with 'Any'/'object' values; define a "
    "TypedDict, dataclass, or model"
)

DICT_BASES = {
    "dict",
    "Dict",
    "Mapping",
    "MutableMapping",
    "defaultdict",
    "OrderedDict",
}


def _is_dict_base(node: ast.expr) -> bool:
    base = dotted_name(node)
    if base is None:
        return False
    return base.split(".")[-1] in DICT_BASES


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Subscript) or not _is_dict_base(node.value):
            continue
        if not isinstance(node.slice, ast.Tuple) or len(node.slice.elts) != 2:
            continue
        value_type = node.slice.elts[1]
        if is_any(value_type) or is_bare_object(value_type):
            yield node.lineno, node.col_offset, MESSAGE
