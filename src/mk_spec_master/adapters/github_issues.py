"""Adapter for GitHub Issues. SPEC_PROJECT_KEY=owner/repo.

Auth resolution order:
    1. GITHUB_TOKEN env var (preferred for CI / server use)
    2. `gh auth token` on PATH (preferred for local dev — reuses gh CLI auth)
"""

from . import register
from .base import SpecSource, Spec, SpecSummary


@register("github_issues")
class GitHubIssuesAdapter(SpecSource):
    name = "github_issues"

    def list_specs(self, **filters):
        # TODO(v0.1): call GitHub REST/GraphQL via `gh api` or requests.
        raise NotImplementedError("github_issues.list_specs — v0.1")

    def fetch(self, spec_id: str) -> Spec:
        # TODO(v0.1): GET /repos/{owner}/{repo}/issues/{number}.
        raise NotImplementedError("github_issues.fetch — v0.1")
