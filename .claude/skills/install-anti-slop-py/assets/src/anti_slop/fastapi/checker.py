"""Flake8 entry point for the opt-in FastAPI rule group (ASF)."""

from __future__ import annotations

import ast
from collections.abc import Iterator

from anti_slop import __version__
from anti_slop.context import Context
from anti_slop.fastapi import adhoc_response, manual_parsing, response_contract

RULES = [
    response_contract.check,
    manual_parsing.check,
    adhoc_response.check,
]


class AntiSlopFastapiChecker:
    name = "anti-slop-fastapi"
    version = __version__
    # Framework policy stays opt-in when installed from PyPI: enable with
    # `enable-extensions = ASF` in repos that use fastapi.
    off_by_default = True

    def __init__(self, tree: ast.AST, lines: list[str]) -> None:
        self._tree = tree
        self._lines = lines

    def run(self) -> Iterator[tuple[int, int, str, type[AntiSlopFastapiChecker]]]:
        context = Context(tree=self._tree, lines=self._lines, allow_typeguards=False)
        for rule in RULES:
            for lineno, col, message in rule(context):
                yield lineno, col, message, type(self)
