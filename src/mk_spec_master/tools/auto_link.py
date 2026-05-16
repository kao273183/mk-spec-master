"""auto_link_tests — scan test files for `@spec:` tags and populate the
traceability index without the AI client having to issue link calls
per scenario.

Conventions supported (all case-insensitive on the marker, exact match
on the spec id):

  Python              JS / TS                  Go
  -------------       --------------           ----------------
  # @spec: LIN-123    // @spec: LIN-123        // @spec: LIN-123
  '''                 /**                      // @spec LIN-123
  @spec: LIN-123       * @spec LIN-123
  '''                  */

For each `@spec:` tag, we look upward (up to 30 lines) for the nearest
test function signature — `def test_*` in Python, or `it('...', ...)` /
`test('...', ...)` in JS/TS — and emit a test_node_id of the form
`<relative-path>::<test-name>`.

v0.3.2 covers the 95% case. Nested describe/context blocks, pytest
class methods (TestX::test_y), and Go `func TestX(t *testing.T)` come
in v0.4 if anyone asks.
"""

import re
from pathlib import Path
from typing import Any

from .. import config
from . import coverage as coverage_tools


# Spec id marker. Tightly defined: starts with a letter, allows letters /
# digits / hyphens / underscores. Tolerates "@spec LIN-123" *and*
# "@spec: LIN-123" *and* "@spec:LIN-123".
_SPEC_TAG_RE = re.compile(
    r"@spec\s*:?\s*([A-Za-z][\w-]*)",
    re.IGNORECASE,
)

# Python test function declaration.
_PY_TEST_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(")

# JS / TS `it('name', ...)` / `test('name', ...)`.
_JS_TEST_RE = re.compile(
    r"^\s*(?:it|test)\s*\(\s*['\"`](?P<name>[^'\"`]+)['\"`]"
)

# Go `func TestX(t *testing.T)`.
_GO_TEST_RE = re.compile(r"^\s*func\s+(Test\w+)\s*\(")


def _detect_language(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".py":
        return "python"
    if suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs"}:
        return "js"
    if suffix == ".go":
        return "go"
    return "unknown"


def _match_test_decl(line: str, language: str) -> str | None:
    if language == "python":
        m = _PY_TEST_RE.match(line)
        return m.group(1) if m else None
    if language == "js":
        m = _JS_TEST_RE.match(line)
        return m.group("name") if m else None
    if language == "go":
        m = _GO_TEST_RE.match(line)
        return m.group(1) if m else None
    return None


def _test_name_near(lines: list[str], tag_line_idx: int, language: str) -> str | None:
    """Return the nearest test declaration name. Both conventions need
    to work:

      - `@spec:` inside a docstring  → test_decl is ABOVE the tag
      - `@spec:` in a comment above  → test_decl is BELOW the tag

    We scan both directions and pick the closer match (by line
    distance), so a tag sitting between two functions binds to the one
    it's literally next to instead of always preferring one side.
    """
    n = len(lines)
    best_name: str | None = None
    best_distance = 999

    for offset in range(1, 11):
        i = tag_line_idx + offset
        if 0 <= i < n:
            name = _match_test_decl(lines[i], language)
            if name:
                if offset < best_distance:
                    best_name = name
                    best_distance = offset
                break

    for offset in range(0, 31):
        i = tag_line_idx - offset
        if 0 <= i < n:
            name = _match_test_decl(lines[i], language)
            if name:
                if offset < best_distance:
                    best_name = name
                    best_distance = offset
                break

    return best_name


def _scan_file(path: Path, base: Path, language: str) -> list[dict]:
    """Return discoveries for one file. Empty if the file has no @spec
    tags or no detectable test surrounding any tag."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeDecodeError):
        return []

    lines = text.splitlines()
    rel_path = path.relative_to(base).as_posix()
    out: list[dict] = []
    for m in _SPEC_TAG_RE.finditer(text):
        spec_id = m.group(1)
        # Skip generic noise — common false-positive trigger is the
        # word "spec" itself (e.g. "@spec is a marker..."). Require the
        # captured id to look like a real ticket key (uppercase letter
        # somewhere or a hyphen-digit pattern).
        if not re.search(r"[A-Z]|-\d", spec_id):
            continue
        tag_line_idx = text.count("\n", 0, m.start())
        test_name = _test_name_near(lines, tag_line_idx, language)
        if not test_name:
            continue
        out.append(
            {
                "file": rel_path,
                "test_node_id": f"{rel_path}::{test_name}",
                "spec_id": spec_id,
                "line": tag_line_idx + 1,
            }
        )
    return out


def _build_markdown(payload: dict) -> str:
    rows = payload["discoveries"]
    lines = [
        "# Auto-link report",
        "",
        f"- Test directory: `{payload['test_dir']}`",
        f"- Files scanned: {payload['files_scanned']}",
        f"- `@spec:` tags found: {payload['tags_found']}",
        f"- Links added: {payload['links_added']}",
        f"- Links updated: {payload['links_updated']}",
        f"- Skipped (no matching test function): {payload['skipped']}",
    ]
    if payload["dry_run"]:
        lines.append("- **dry_run=true — no writes made**")
    lines.append("")

    if rows:
        lines.append("| Test | Spec | File:Line |")
        lines.append("|---|---|---|")
        for d in rows:
            lines.append(
                f"| `{d['test_node_id'].split('::')[-1]}` | `{d['spec_id']}` | `{d['file']}:{d['line']}` |"
            )
    else:
        lines.append("_No `@spec:` tags discovered. Add `@spec: <ID>` in a docstring or comment near each test._")
    return "\n".join(lines)


def auto_link_tests_tool(arguments: dict) -> dict[str, Any]:
    """Scan a directory for test files with `@spec:` tags and populate
    the traceability index.

    Args:
        test_dir   absolute path to scan. Defaults to
                   SPEC_PROJECT_ROOT/tests, then SPEC_PROJECT_ROOT.
        languages  list of "python" / "js" / "go"; default all three.
        dry_run    bool. When true, report what would be linked without
                   touching the index.
    """
    explicit_dir = arguments.get("test_dir")
    dry_run = bool(arguments.get("dry_run"))
    languages = arguments.get("languages") or ["python", "js", "go"]
    if isinstance(languages, str):
        languages = [languages]

    if explicit_dir:
        base = Path(explicit_dir).expanduser().resolve()
    else:
        candidate = config.PROJECT_ROOT / "tests"
        base = candidate if candidate.exists() else config.PROJECT_ROOT

    if not base.exists() or not base.is_dir():
        return {"error": f"test_dir does not exist or is not a directory: {base}"}

    suffixes_by_lang = {
        "python": [".py"],
        "js": [".js", ".jsx", ".ts", ".tsx", ".mjs"],
        "go": [".go"],
    }
    wanted_suffixes: set[str] = set()
    for lang in languages:
        wanted_suffixes.update(suffixes_by_lang.get(lang, []))

    discoveries: list[dict] = []
    files_scanned = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in wanted_suffixes:
            continue
        files_scanned += 1
        language = _detect_language(path)
        discoveries.extend(_scan_file(path, base, language))

    added = updated = 0
    skipped = 0
    if not dry_run:
        for d in discoveries:
            result = coverage_tools.link_test_to_spec_tool(
                {"spec_id": d["spec_id"], "test_node_id": d["test_node_id"]}
            )
            action = result.get("action")
            if action == "added":
                added += 1
            elif action == "updated":
                updated += 1
            else:
                skipped += 1

    payload = {
        "test_dir": str(base),
        "files_scanned": files_scanned,
        "tags_found": len(discoveries),
        "links_added": added,
        "links_updated": updated,
        "skipped": skipped,
        "dry_run": dry_run,
        "discoveries": discoveries,
    }
    payload["markdown"] = _build_markdown(payload)
    return payload
