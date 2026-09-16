"""Opt-in FastAPI rule group (ASF).

Enable only in repositories that declare `fastapi` as a direct dependency,
or on explicit user request. Runs alongside Ruff's ready-made `FAST` rules
(FAST001–003) and `ASYNC` rules (blocking I/O in async routes); the ASF
rules cover only the response-contract and boundary-parsing gaps.
"""
