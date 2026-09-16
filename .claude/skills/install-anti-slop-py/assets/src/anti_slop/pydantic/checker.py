"""Flake8 entry point for the opt-in Pydantic rule group (ASD)."""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop import __version__
from anti_slop.context import Context
from anti_slop.pydantic import (
    adapter_scope,
    any_fields,
    construct_safety,
    dump_widening,
    extra_allow,
)

RULES = [
    construct_safety.check,
    extra_allow.check,
    any_fields.check,
    dump_widening.check,
    adapter_scope.check,
]


class AntiSlopPydanticChecker:
    name = "anti-slop-pydantic"
    version = __version__
    # Framework policy stays opt-in when installed from PyPI: enable with
    # `enable-extensions = ASD` in repos that use pydantic.
    off_by_default = True

    def __init__(self, tree: ast.AST, lines: list[str]) -> None:
        self._tree = tree
        self._lines = lines

    def run(self) -> Iterator[tuple[int, int, str, type[AntiSlopPydanticChecker]]]:
        context = Context(tree=self._tree, lines=self._lines, allow_typeguards=False)
        for rule in RULES:
            for lineno, col, message in rule(context):
                yield lineno, col, message, type(self)
