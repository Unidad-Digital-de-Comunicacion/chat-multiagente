"""Flake8 entry point dispatching every anti-slop rule."""

from __future__ import annotations

import argparse
import ast
import contextlib
from collections.abc import Iterator
from typing import TYPE_CHECKING

from anti_slop import __version__, rules
from anti_slop.context import Context

if TYPE_CHECKING:
    from flake8.options.manager import OptionManager

__all__ = ["AntiSlopChecker", "Context"]


class AntiSlopChecker:
    name = "anti-slop"
    version = __version__

    allow_typeguards = False

    def __init__(self, tree: ast.AST, lines: list[str]) -> None:
        self._tree = tree
        self._lines = lines

    @classmethod
    def add_options(cls, parser: OptionManager) -> None:
        # A repo can load this plugin twice at once: from the installed
        # package's entry points and from a vendored local-plugins copy
        # (typical mid-migration). Registering the flag twice raises, so the
        # second registration is dropped instead of crashing flake8.
        with contextlib.suppress(argparse.ArgumentError):
            parser.add_option(
                "--anti-slop-allow-typeguards",
                action="store_true",
                parse_from_config=True,
                default=False,
                help="Allow isinstance/hasattr narrowing inside TypeGuard/TypeIs "
                "functions (relaxes ASP002).",
            )

    @classmethod
    def parse_options(cls, options: argparse.Namespace) -> None:
        cls.allow_typeguards = options.anti_slop_allow_typeguards

    def run(self) -> Iterator[tuple[int, int, str, type[AntiSlopChecker]]]:
        context = Context(
            tree=self._tree,
            lines=self._lines,
            allow_typeguards=self.allow_typeguards,
        )
        for rule in rules.ALL:
            for lineno, col, message in rule(context):
                yield lineno, col, message, type(self)
