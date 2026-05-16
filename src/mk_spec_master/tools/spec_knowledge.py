"""Spec-knowledge layer.

Mirrors mk-qa-master's QA knowledge pattern: a markdown file at
SPEC_PROJECT_ROOT/spec-knowledge.md carries methodology (EARS,
INVEST, AC quality rules) plus the team's domain-specific spec
conventions. parse_spec / extract_scenarios stay heuristic — they
don't read this file directly — but the AI client should call
`get_spec_context` near the start of a session so the same rules
guide every spec it touches.

init_spec_knowledge   writes a starter file (idempotent — never
                      overwrites unless overwrite=True).
get_spec_context      reads the file (or built-in defaults), optionally
                      filtered by a section header for partial pulls.
"""

import re
from typing import Any

from .. import config


# Built-in starter content. Two halves:
#   1. Universal methodology — EARS, INVEST, AC quality rules. Same
#      across teams.
#   2. TODO sections — domain rules / actors / glossary. Empty placeholders
#      that the project lead fills in.

_UNIVERSAL_METHODOLOGY = """\
## Universal spec methodology

### EARS (Easy Approach to Requirements Syntax)

Every acceptance criterion should collapse to one of these patterns:

- **Ubiquitous:**   The system shall <response>.
- **Event-driven:** When <trigger>, the system shall <response>.
- **State-driven:** While <state>, the system shall <response>.
- **Optional:**     Where <feature is enabled>, the system shall <response>.
- **Unwanted:**     If <trigger>, then the system shall <response>.

Each pattern collapses to a single testable claim — no ambiguity about
scope, trigger, or response.

### INVEST (story-level — for the spec as a whole)

- **Independent**  — can ship without sequencing against other specs
- **Negotiable**   — the *what* is fixed, the *how* is flexible
- **Valuable**     — observable to a user or stakeholder
- **Estimable**    — engineering has enough detail to size it
- **Small**        — fits one sprint; otherwise split
- **Testable**     — every AC has a pass/fail outcome

### AC quality rules

1. **Observable** — describes user-visible behaviour, not internal mechanism.
   Bad: "Uses Redis for caching."  Good: "Page loads in under 200ms p95."
2. **Measurable** — every fuzzy word ("fast", "easy", "intuitive") replaced
   by a threshold or signal.
3. **Atomic** — one assertion per AC; split compound clauses.
4. **Scoped** — preconditions + actor + trigger + expected outcome.
5. **Negative-aware** — at least one error / edge AC per happy path AC.
"""

_DOMAIN_TODO_SECTIONS = """\
## Your domain rules
- TODO: business invariants the system must hold (e.g., \"a user cannot apply
  more than one promo code per order\", \"refunds must be issued within 14 days\").

## Your actors
- TODO: who interacts with the system (logged-in user, admin, guest, ops, …)
  and the canonical way to set each up in tests.

## Your regression hot-zones
- TODO: features that historically break (auth, payment, search, …) — tests
  here get extra edge-case coverage.

## Your glossary
- TODO: domain terms with one-line definitions (the canonical \"Order\",
  \"Customer\", \"Subscription\" — whatever your business calls them).

## Your test environment
- TODO: how tests authenticate, where data lives, what seed users / fixtures
  are reusable across specs.
"""


_HEADING_RE = re.compile(r"^\s*#{1,6}\s*(.+?)\s*$", re.MULTILINE)


def _knowledge_path():
    return config.PROJECT_ROOT / "spec-knowledge.md"


def _starter_content(project_name: str) -> str:
    return (
        f"# Spec knowledge — {project_name}\n\n"
        "> Methodology + domain glossary that mk-spec-master tools "
        "(`analyze_spec_quality`, `propose_spec_improvements`, "
        "`get_optimization_plan`) lean on indirectly. The AI client should "
        "call `get_spec_context` near the start of each session so the same "
        "rules colour every spec interpretation that follows.\n\n"
        + _UNIVERSAL_METHODOLOGY
        + "\n"
        + _DOMAIN_TODO_SECTIONS
    )


def init_spec_knowledge_tool(arguments: dict) -> dict[str, Any]:
    """Create SPEC_PROJECT_ROOT/spec-knowledge.md from a starter template.

    Idempotent: refuses to clobber an existing file unless overwrite=True.
    """
    project_name = str(arguments.get("project_name") or config.PROJECT_ROOT.name)
    overwrite = bool(arguments.get("overwrite"))

    path = _knowledge_path()
    if path.exists() and not overwrite:
        return {
            "created": False,
            "path": str(path),
            "reason": "file already exists; pass overwrite=true to replace",
        }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_starter_content(project_name), encoding="utf-8")
    return {
        "created": True,
        "path": str(path),
        "bytes": path.stat().st_size,
    }


def _select_section(content: str, header: str) -> str:
    """Return the substring starting at a heading whose text matches
    `header` (case-insensitive, partial match) until the next heading
    of equal-or-greater depth. Empty string if no match."""
    header_norm = header.strip().lower()
    matches = list(_HEADING_RE.finditer(content))
    for i, m in enumerate(matches):
        text = m.group(1).strip().lower()
        if header_norm in text:
            start = m.start()
            # find depth of this heading
            hashes = re.match(r"^\s*(#+)", content[start:])
            this_depth = len(hashes.group(1)) if hashes else 1
            # find next heading of equal-or-shallower depth
            for nxt in matches[i + 1:]:
                next_hashes = re.match(r"^\s*(#+)", content[nxt.start():])
                next_depth = len(next_hashes.group(1)) if next_hashes else 1
                if next_depth <= this_depth:
                    return content[start:nxt.start()].rstrip() + "\n"
            return content[start:].rstrip() + "\n"
    return ""


def get_spec_context_tool(arguments: dict) -> dict[str, Any]:
    """Read SPEC_PROJECT_ROOT/spec-knowledge.md (or fall back to built-in
    defaults if missing). Optional `section` filters to a single H2/H3
    block (partial-match, case-insensitive).
    """
    section = arguments.get("section")

    path = _knowledge_path()
    if path.exists():
        content = path.read_text(encoding="utf-8")
        source = "file"
    else:
        # Built-in defaults so the AI client still gets *some* methodology
        # even before init_spec_knowledge has been run.
        content = (
            "# Spec knowledge — (built-in defaults; run init_spec_knowledge to customise)\n\n"
            + _UNIVERSAL_METHODOLOGY
            + "\n"
            + _DOMAIN_TODO_SECTIONS
        )
        source = "builtin"

    if section:
        slice_ = _select_section(content, section)
        if not slice_:
            return {
                "source": source,
                "section": section,
                "found": False,
                "content": "",
                "available_sections": [m.group(1).strip() for m in _HEADING_RE.finditer(content)],
            }
        return {
            "source": source,
            "section": section,
            "found": True,
            "content": slice_,
        }

    return {
        "source": source,
        "content": content,
        "byte_count": len(content.encode("utf-8")),
    }
