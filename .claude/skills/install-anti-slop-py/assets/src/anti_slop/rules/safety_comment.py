"""ASP001: every type assertion carries a SAFETY comment.

A `typing.cast` or a `# type: ignore` erases what the type checker knew, so
each one must state the invariant that makes it safe. PGH003 stops at
demanding an error code on ignores; this rule demands the justification
itself. Ports `require-safety-comment-for-type-assertion`.

`cast` is matched by name, which means an aliased import of `typing.cast`
slips through.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.rules.common import comment_map, has_safety_comment, is_cast_call

CODE = "ASP001"
MESSAGE = (
    f"{CODE} type assertion requires a '# SAFETY:' comment on the same or "
    "preceding line documenting the checked invariant"
)

IGNORE_MARKER = "type: ignore"


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    comments = comment_map(context.lines)
    for node in ast.walk(context.tree):
        if not isinstance(node, ast.Call) or not is_cast_call(node.func):
            continue
        if not has_safety_comment(comments, node.lineno):
            yield node.lineno, node.col_offset, MESSAGE
    for lineno, comment in comments.items():
        if IGNORE_MARKER in comment and not has_safety_comment(comments, lineno):
            yield lineno, 0, MESSAGE
