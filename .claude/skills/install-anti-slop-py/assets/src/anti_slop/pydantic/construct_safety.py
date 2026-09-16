"""ASD001: `model_construct()` requires a SAFETY comment.

`model_construct()` and v1's `construct()` skip validation entirely; they
are Pydantic's `cast`. The official docs say to use them only with data
"which has already been validated, or that you definitely trust", so each
call must document that trust, mirroring ASP001.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import comment_map, has_safety_comment

CODE = "ASD001"
MESSAGE = (
    f"{CODE} model_construct() skips validation; add a '# SAFETY:' comment "
    "documenting why the data is already trusted"
)

CONSTRUCT_METHODS = {"model_construct", "construct"}


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    comments = comment_map(context.lines)
    for node in ast.walk(context.tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in CONSTRUCT_METHODS
            and not has_safety_comment(comments, node.lineno)
        ):
            yield node.lineno, node.col_offset, MESSAGE
