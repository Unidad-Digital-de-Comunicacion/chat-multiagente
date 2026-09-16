"""ASD002: no `extra="allow"` model configuration.

`extra="allow"` stores unvalidated keys on the model without any contract.
Stay on the default `"ignore"`, switch to `"forbid"` at strict boundaries,
or model the extra data explicitly.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop.context import Context
from anti_slop.pydantic.common import model_classes

CODE = "ASD002"
MESSAGE = (
    f"{CODE} extra='allow' stores unvalidated keys without a contract; use "
    "'ignore' or 'forbid', or model the extra data explicitly"
)


def _is_config_dict_call(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "ConfigDict"
    if isinstance(node, ast.Attribute):
        return node.attr == "ConfigDict"
    return False


def _allows_extra(value: ast.expr) -> bool:
    if isinstance(value, ast.Constant):
        return value.value == "allow"
    return isinstance(value, ast.Attribute) and value.attr == "allow"


def check(context: Context) -> Iterator[tuple[int, int, str]]:
    for node in ast.walk(context.tree):
        if isinstance(node, ast.Call) and _is_config_dict_call(node.func):
            for keyword in node.keywords:
                if keyword.arg == "extra" and _allows_extra(keyword.value):
                    yield node.lineno, node.col_offset, MESSAGE
    for model in model_classes(context.tree):
        for statement in model.body:
            if not isinstance(statement, ast.ClassDef) or statement.name != "Config":
                continue
            for config_statement in statement.body:
                if not isinstance(config_statement, ast.Assign):
                    continue
                targets_extra = any(
                    isinstance(target, ast.Name) and target.id == "extra"
                    for target in config_statement.targets
                )
                if targets_extra and _allows_extra(config_statement.value):
                    yield (
                        config_statement.lineno,
                        config_statement.col_offset,
                        MESSAGE,
                    )
