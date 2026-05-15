"""Spec source abstraction. One concrete subclass per adapter (markdown_local,
github_issues, linear, jira, notion, figma)."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SpecSummary:
    """Lightweight listing entry — id + title + url + status."""

    id: str
    title: str
    url: str = ""
    status: str = ""
    labels: list[str] = field(default_factory=list)


@dataclass
class Spec:
    """Full spec record returned by fetch()."""

    id: str
    title: str
    body: str  # Raw natural-language body — parsing happens downstream.
    url: str = ""
    status: str = ""
    labels: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class SpecSource(ABC):
    """Implementations must be inexpensive to instantiate (no network on init).
    Network calls happen inside list_specs / fetch."""

    name: str = "base"

    @abstractmethod
    def list_specs(self, **filters) -> list[SpecSummary]:
        """Filters: status, label, limit. Adapters may accept extra source-
        specific kwargs."""

    @abstractmethod
    def fetch(self, spec_id: str) -> Spec:
        """Return full spec content. Raises ValueError if spec_id is unknown."""
