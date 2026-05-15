"""Adapter for GitHub Issues. SPEC_PROJECT_KEY=owner/repo.

v0.1 uses the `gh` CLI as a subprocess: zero new dependencies, reuses the
user's existing `gh auth login` credentials, works the same on local dev
and GitHub Actions runners (which ship `gh` preinstalled).

If GITHUB_TOKEN env is set, gh CLI picks it up automatically. Otherwise it
falls back to whatever `gh auth login` configured.

Spec ids look like "123" — the issue number. Internally we use
"<owner>/<repo>#<number>" if needed for cross-repo disambiguation, but
v0.1 sticks to a single repo per process.
"""

import json
import shutil
import subprocess

from ..config import SOURCE_KEY
from . import register
from .base import Spec, SpecSource, SpecSummary


class GhUnavailable(RuntimeError):
    """Raised when `gh` CLI is missing or unauthenticated. The error message
    is what the AI client will surface to the user, so it should be actionable."""


def _gh_path() -> str:
    path = shutil.which("gh")
    if not path:
        raise GhUnavailable(
            "github_issues adapter requires the `gh` CLI on PATH. "
            "Install from https://cli.github.com/ then `gh auth login`."
        )
    return path


def _gh_api(endpoint: str, *, paginate: bool = False) -> list | dict:
    """Run `gh api <endpoint>` and return parsed JSON. Raises GhUnavailable
    on auth failures with the underlying stderr appended."""
    cmd = [_gh_path(), "api", endpoint]
    if paginate:
        cmd.append("--paginate")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise GhUnavailable(
            f"`gh api {endpoint}` failed (exit {proc.returncode}). "
            f"stderr: {proc.stderr.strip() or '(empty)'}"
        )

    raw = proc.stdout.strip()
    if not raw:
        return [] if paginate else {}

    if not paginate:
        return json.loads(raw)

    # --paginate concatenates JSON arrays from each page; gh emits them
    # as a single bracketed array, so a plain loads is fine.
    return json.loads(raw)


def _owner_repo() -> str:
    if "/" not in SOURCE_KEY:
        raise ValueError(
            f"github_issues adapter requires SPEC_PROJECT_KEY=owner/repo, got {SOURCE_KEY!r}"
        )
    return SOURCE_KEY


@register("github_issues")
class GitHubIssuesAdapter(SpecSource):
    name = "github_issues"

    def list_specs(self, **filters) -> list[SpecSummary]:
        owner_repo = _owner_repo()

        state = filters.get("status", "open")  # 'open' | 'closed' | 'all'
        label_filter = filters.get("label")
        limit = int(filters.get("limit", 50))

        # `per_page=100` + page-1 only — keeps the call cheap; users hitting
        # the 100 ceiling can pass a tighter label filter or wait for v0.2's
        # cursor-aware variant.
        endpoint = (
            f"repos/{owner_repo}/issues?state={state}&per_page={min(limit, 100)}"
        )
        if label_filter:
            endpoint += f"&labels={label_filter}"

        data = _gh_api(endpoint)
        if not isinstance(data, list):
            return []

        out: list[SpecSummary] = []
        for issue in data:
            # GitHub returns PRs in the issues endpoint — skip them.
            if "pull_request" in issue:
                continue
            number = issue.get("number")
            if number is None:
                continue
            out.append(
                SpecSummary(
                    id=str(number),
                    title=str(issue.get("title", "")),
                    url=str(issue.get("html_url", "")),
                    status=str(issue.get("state", "")),
                    labels=[lbl.get("name", "") for lbl in issue.get("labels", []) if isinstance(lbl, dict)],
                )
            )
            if len(out) >= limit:
                break
        return out

    def fetch(self, spec_id: str) -> Spec:
        owner_repo = _owner_repo()
        issue = _gh_api(f"repos/{owner_repo}/issues/{spec_id}")
        if not isinstance(issue, dict) or "number" not in issue:
            raise ValueError(f"github_issues: issue {spec_id} not found in {owner_repo}")

        labels = [lbl.get("name", "") for lbl in issue.get("labels", []) if isinstance(lbl, dict)]
        return Spec(
            id=str(issue["number"]),
            title=str(issue.get("title", "")),
            body=str(issue.get("body") or ""),
            url=str(issue.get("html_url", "")),
            status=str(issue.get("state", "")),
            labels=labels,
            metadata={
                "author": (issue.get("user") or {}).get("login", ""),
                "created_at": issue.get("created_at", ""),
                "updated_at": issue.get("updated_at", ""),
                "comments": issue.get("comments", 0),
            },
        )
