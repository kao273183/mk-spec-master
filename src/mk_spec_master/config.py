"""Env-var-driven config. Mirrors mk-qa-master's pattern."""

from pathlib import Path
import os

PROJECT_ROOT = Path(os.getenv("SPEC_PROJECT_ROOT", "./spec_project")).resolve()

SOURCE_NAME = os.getenv("SPEC_SOURCE", "markdown_local").lower()

# Source-specific key. For github_issues this is "owner/repo"; for Linear it is
# a team id; for JIRA a board id; for markdown_local it is ignored.
SOURCE_KEY = os.getenv("SPEC_PROJECT_KEY", "")

# Adapter auth tokens. Each adapter reads only the ones it needs.
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL", "")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN", "")

# Traceability index location. One JSON file under PROJECT_ROOT keeps the
# spec↔test mapping; data ownership stays with the user.
INDEX_DIR = PROJECT_ROOT / ".mk-spec-master"
INDEX_PATH = INDEX_DIR / "index.json"

# Where local markdown specs live (markdown_local adapter only).
SPECS_DIR = PROJECT_ROOT / "specs"
