"""Locate the bundled skill directory and the bw-agent wrapper."""

from __future__ import annotations

import os
from pathlib import Path

_PKG_DIR = Path(__file__).resolve().parent


def skill_dir() -> Path:
    """Directory containing ``SKILL.md`` (the portable Agent Skill).

    Resolution: the copy bundled in the wheel, then the repository checkout
    (editable installs / running from source).
    """
    for candidate in (_PKG_DIR / "_skill" / "bitwarden", _PKG_DIR.parents[1] / "skill" / "bitwarden"):
        if (candidate / "SKILL.md").is_file():
            return candidate
    raise FileNotFoundError("bundled Bitwarden skill directory not found; reinstall skill-bitwarden")


def skills_root() -> Path:
    """Parent directory that contains the ``bitwarden/`` skill folder.

    Pass this to harnesses that scan a *directory of skills* (e.g. deepagents
    ``create_deep_agent(skills=[...])``).
    """
    return skill_dir().parent


def wrapper_path() -> Path:
    """Path to the ``bw-agent`` script (``$BW_AGENT_BIN`` overrides)."""
    override = os.environ.get("BW_AGENT_BIN")
    if override:
        return Path(override)
    return skill_dir() / "scripts" / "bw-agent"
