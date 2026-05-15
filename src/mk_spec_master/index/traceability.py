"""Read/write the traceability index. Shape documented in docs/prd.md §9.

Module attributes on `config` are looked up at call time (not bound at
import time) so tests can monkeypatch INDEX_PATH / INDEX_DIR cleanly.
"""

import json

from .. import config

EMPTY_INDEX: dict = {
    "version": 1,
    "specs": {},
    "orphans": [],
}


def load_index() -> dict:
    if not config.INDEX_PATH.exists():
        return dict(EMPTY_INDEX)
    return json.loads(config.INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict) -> None:
    config.INDEX_DIR.mkdir(parents=True, exist_ok=True)
    config.INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
