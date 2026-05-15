"""Read/write the traceability index. Shape documented in docs/prd.md §9.

Module attributes on `config` are looked up at call time (not bound at
import time) so tests can monkeypatch INDEX_PATH / INDEX_DIR cleanly.
"""

import json

from .. import config


def _empty_index() -> dict:
    """Fresh empty index each call. Was previously a module-level dict,
    but shallow-copying it leaked the nested `specs` reference across
    callers — one test's writes appearing in the next test's "fresh" load."""
    return {"version": 1, "specs": {}, "orphans": []}


# Kept for backwards compatibility with any external import of the constant.
# Treat as read-only; do not mutate. Use _empty_index() internally.
EMPTY_INDEX: dict = _empty_index()


def load_index() -> dict:
    if not config.INDEX_PATH.exists():
        return _empty_index()
    return json.loads(config.INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict) -> None:
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    config.INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
