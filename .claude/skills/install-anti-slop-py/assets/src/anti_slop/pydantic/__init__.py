"""Opt-in Pydantic rule group (ASD).

Enable only in repositories that declare `pydantic` as a direct dependency,
or on explicit user request. Runs alongside `flake8-pydantic` (PYD hygiene
rules) and the official Pydantic mypy plugin; the ASD rules cover only the
evidence-discipline gaps neither of those enforces.
"""
