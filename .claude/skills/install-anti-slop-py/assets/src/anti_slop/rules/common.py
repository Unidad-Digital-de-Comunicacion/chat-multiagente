"""Shared AST helpers for anti-slop rules."""

from __future__ import annotations

import ast
import io
import tokenize

SAFETY_MARKER = "# SAFETY:"


def comment_map(lines: list[str]) -> dict[int, str]:
    """Map line number to the comment on that line, via real tokenization so
    markers inside string literals never count as comments."""
    comments: dict[int, str] = {}
    reader = io.StringIO("".join(lines)).readline
    try:
        for token in tokenize.generate_tokens(reader):
            if token.type == tokenize.COMMENT:
                comments[token.start[0]] = token.string
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass
    return comments


def has_safety_comment(comments: dict[int, str], lineno: int) -> bool:
    """True when the line or the one above carries a SAFETY comment."""
    return SAFETY_MARKER in comments.get(lineno, "") or SAFETY_MARKER in comments.get(
        lineno - 1, ""
    )


def dotted_name(node: ast.expr) -> str | None:
    """Flatten an attribute chain like `unittest.mock.patch` into a string."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return ".".join(reversed(parts))
    return None


def is_cast_call(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "cast"
    if isinstance(node, ast.Attribute):
        return node.attr == "cast"
    return False


def is_any(node: ast.AST) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "Any"
    if isinstance(node, ast.Attribute):
        return node.attr == "Any"
    return False


def is_bare_object(node: ast.expr | None) -> bool:
    return isinstance(node, ast.Name) and node.id == "object"


def function_nodes(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
