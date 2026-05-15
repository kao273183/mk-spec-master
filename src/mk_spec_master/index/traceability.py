"""Read/write the traceability index. Shape documented in docs/prd.md §9."""

import json

from ..config import INDEX_DIR, INDEX_PATH

EMPTY_INDEX: dict = {
    "version": 1,
    "specs": {},
    "orphans": [],
}


def load_index() -> dict:
    if not INDEX_PATH.exists():
        return dict(EMPTY_INDEX)
    return json.loads(INDEX_PATH.read_text(encoding="utf-8"))


def save_index(index: dict) -> None:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    INDEX_PATH.write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
