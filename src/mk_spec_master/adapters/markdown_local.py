"""Adapter for local Markdown spec files. SPEC_PROJECT_ROOT/specs/*.md.

Frontmatter (YAML-ish) drives metadata:

    ---
    id: SPEC-001
    title: Apply discount at checkout
    status: in-progress
    labels: [checkout, billing]
    ---

    ## Acceptance criteria
    1. Logged-in user enters valid promo code → discount applied...

Why hand-rolled instead of pyyaml: keeps the dep list to mcp>=1.0.0 only.
The frontmatter shape is constrained (scalars + inline lists), so a tiny
parser is enough. If users need nested dicts, they can switch to a JSON
codeblock convention or we add pyyaml in v0.2.
"""

import re
from pathlib import Path

from ..config import SPECS_DIR
from . import register
from .base import Spec, SpecSource, SpecSummary

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z",
    re.DOTALL,
)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Returns (metadata_dict, body). If no frontmatter, returns ({}, full_text)."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    meta_block, body = m.group(1), m.group(2)
    meta: dict = {}
    for raw_line in meta_block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        meta[key] = _coerce(value)
    return meta, body


def _coerce(value: str):
    """Parse scalars + inline lists. Bool / null / int kept simple."""
    if value == "" or value.lower() == "null":
        return None
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("\"'") for item in inner.split(",")]
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    return value.strip("\"'")


def _spec_files() -> list[Path]:
    if not SPECS_DIR.exists():
        return []
    return sorted(SPECS_DIR.glob("*.md"))


def _spec_id_from(meta: dict, fallback_path: Path) -> str:
    """Prefer explicit `id` in frontmatter; else derive from filename stem."""
    return str(meta.get("id") or fallback_path.stem)


@register("markdown_local")
class MarkdownLocalAdapter(SpecSource):
    name = "markdown_local"

    def list_specs(self, **filters) -> list[SpecSummary]:
        status_filter = filters.get("status")
        label_filter = filters.get("label")
        limit = filters.get("limit", 50)

        out: list[SpecSummary] = []
        for path in _spec_files():
            try:
                meta, _ = _parse_frontmatter(path.read_text(encoding="utf-8"))
            except OSError:
                continue

            spec_id = _spec_id_from(meta, path)
            title = str(meta.get("title") or spec_id)
            status = str(meta.get("status") or "")
            labels = meta.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]

            if status_filter and status != status_filter:
                continue
            if label_filter and label_filter not in labels:
                continue

            out.append(
                SpecSummary(
                    id=spec_id,
                    title=title,
                    url=str(path),
                    status=status,
                    labels=list(labels),
                )
            )
            if len(out) >= limit:
                break
        return out

    def fetch(self, spec_id: str) -> Spec:
        for path in _spec_files():
            meta, body = _parse_frontmatter(path.read_text(encoding="utf-8"))
            if _spec_id_from(meta, path) != spec_id:
                continue

            labels = meta.get("labels") or []
            if isinstance(labels, str):
                labels = [labels]

            return Spec(
                id=spec_id,
                title=str(meta.get("title") or spec_id),
                body=body.strip(),
                url=str(path),
                status=str(meta.get("status") or ""),
                labels=list(labels),
                metadata={k: v for k, v in meta.items() if k not in {"id", "title", "status", "labels"}},
            )

        raise ValueError(f"spec_id={spec_id!r} not found under {SPECS_DIR}")
