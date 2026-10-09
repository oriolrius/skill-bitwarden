#!/usr/bin/env python3
"""Validate an Agent Skill directory against the Agent Skills spec basics.

Checks: SKILL.md frontmatter present; ``name`` matches the directory and
``^[a-z0-9]+(-[a-z0-9]+)*$`` (<= 64 chars); ``description`` 1..1024 chars;
``compatibility`` <= 500 chars; relative ``scripts/`` and ``references/``
paths mentioned in the body exist; scripts are executable; no absolute
home-directory paths.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---\n"):
        raise ValueError("SKILL.md must start with a '---' frontmatter block")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError("unterminated frontmatter")
    meta: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta, text[end + 5 :]


def validate(skill: Path) -> list[str]:
    errors: list[str] = []
    md = skill / "SKILL.md"
    if not md.is_file():
        return [f"{md}: missing"]
    try:
        meta, body = parse_frontmatter(md.read_text())
    except ValueError as exc:
        return [f"{md}: {exc}"]
    name = meta.get("name", "")
    if not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", name) or len(name) > 64:
        errors.append(f"invalid name {name!r}")
    if name != skill.name:
        errors.append(f"name {name!r} must match directory {skill.name!r}")
    desc = meta.get("description", "")
    if not 1 <= len(desc) <= 1024:
        errors.append(f"description length {len(desc)} not in 1..1024")
    if len(meta.get("compatibility", "")) > 500:
        errors.append("compatibility longer than 500 chars")
    for ref in sorted(set(re.findall(r"(?<![\w/<>-])((?:scripts|references)/[A-Za-z0-9._-]+)", body))):
        if not (skill / ref).exists():
            errors.append(f"referenced file does not exist: {ref}")
    for script in (skill / "scripts").glob("*"):
        if script.is_file() and not os.access(script, os.X_OK):
            errors.append(f"script not executable: {script.relative_to(skill)}")
    for f in skill.rglob("*"):
        if f.is_file() and re.search(r"/home/(?!user\b)[a-z]|/Users/[A-Z]", f.read_text(errors="ignore")):
            errors.append(f"absolute personal path in {f.relative_to(skill)}")
    return errors


def main(argv: list[str]) -> int:
    rc = 0
    for d in argv or ["skill/bitwarden"]:
        errs = validate(Path(d))
        for e in errs:
            print(f"{d}: {e}")
        rc |= bool(errs)
        if not errs:
            print(f"{d}: OK")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
