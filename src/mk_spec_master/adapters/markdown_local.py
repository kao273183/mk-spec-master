"""Adapter for local Markdown spec files. SPEC_PROJECT_ROOT/specs/*.md.

Frontmatter (YAML) drives metadata:

    ---
    id: SPEC-001
    title: Apply discount at checkout
    status: in-progress
    labels: [checkout, billing]
    ---

    ## Acceptance criteria
    1. Logged-in user enters valid promo code → discount applied...
"""

from . import register
from .base import SpecSource, Spec, SpecSummary


@register("markdown_local")
class MarkdownLocalAdapter(SpecSource):
    name = "markdown_local"

    def list_specs(self, **filters):
        # TODO(v0.1): glob SPECS_DIR/*.md, parse frontmatter, return summaries.
        raise NotImplementedError("markdown_local.list_specs — v0.1")

    def fetch(self, spec_id: str) -> Spec:
        # TODO(v0.1): read the matching .md file, split frontmatter from body.
        raise NotImplementedError("markdown_local.fetch — v0.1")
