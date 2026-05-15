"""Traceability index: spec ↔ test mapping persisted as JSON."""

from .traceability import load_index, save_index, EMPTY_INDEX

__all__ = ["load_index", "save_index", "EMPTY_INDEX"]
