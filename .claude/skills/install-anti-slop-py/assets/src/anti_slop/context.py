"""Per-file context handed to every rule."""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    tree: ast.AST
    lines: list[str]
    allow_typeguards: bool
