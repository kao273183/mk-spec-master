"""Test config — set env vars before mk_spec_master imports anywhere.

Points SPEC_PROJECT_ROOT at ./examples so the markdown_local adapter sees
examples/specs/*.md as its corpus. This doubles as dogfood:
fixture data and the shipped example never drift apart.
"""

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

os.environ.setdefault("SPEC_SOURCE", "markdown_local")
os.environ.setdefault("SPEC_PROJECT_ROOT", str(REPO_ROOT / "examples"))

# Make src/ importable without `pip install -e .` for local quick runs.
sys.path.insert(0, str(REPO_ROOT / "src"))
