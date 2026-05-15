"""Adapter registry. Mirrors mk-qa-master's runners/ pattern."""

from .base import SpecSource

REGISTRY: dict[str, type[SpecSource]] = {}


def register(name: str):
    def deco(cls):
        REGISTRY[name] = cls
        return cls

    return deco


def get_source(name: str) -> SpecSource:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown SPEC_SOURCE={name!r}. Available: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]()


# Side-effect imports register the concrete adapters into REGISTRY.
from . import markdown_local  # noqa: E402, F401
from . import github_issues  # noqa: E402, F401
from . import linear  # noqa: E402, F401
