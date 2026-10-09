#!/usr/bin/env python3
"""Block environment-specific / personal data from entering this public repo.

Complements gitleaks (which finds *secrets*) by finding *identifying
information*: real hostnames, emails, private IPs, home paths, real-looking
UUIDs, committed config files, plus any string in a private denylist.

Usage:
    check_public_safety.py [FILES...]   check the given files (pre-commit)
    check_public_safety.py --all        check every tracked file
    check_public_safety.py --history    check every line ever added + author/committer emails

Private denylist (never committed): one case-insensitive regex per line in
``.public-safety-denylist`` (gitignored) and/or the ``PUBLIC_SAFETY_DENYLIST``
environment variable (newline separated; set it from a CI secret).
Suppress a reviewed false positive with the marker ``public-safety: allow``
on the same line.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOW_MARKER = "public-safety: allow"

ALLOWED_DOMAINS = {
    # placeholders (RFC 2606 / 6761)
    "example.com",
    "example.org",
    "example.net",
    "example",
    "test",
    "invalid",
    "localhost",
    # Bitwarden public services & docs
    "bitwarden.com",
    "bitwarden.eu",
    # model providers / harness docs referenced in docs
    "deepseek.com",
    "langchain.com",
    "openai.com",
    "anthropic.com",
    "agentskills.io",
    # tooling
    "github.com",
    "githubusercontent.com",
    "gitleaks.io",
    "pre-commit.com",
    "shellcheck.net",
    "astral.sh",
    "pypi.org",
    "pythonhosted.org",
    "python.org",
    "nodejs.org",
    "npmjs.com",
    "json-schema.org",
    "keepachangelog.com",
    "semver.org",
    "opensource.org",
    "conventionalcommits.org",
    "vaultwarden.net",
    "docs.docker.com",
    "brew.sh",
    "snapcraft.io",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)")
URL_RE = re.compile(r"\b[a-z][a-z0-9+.-]*://(?:[^@/\s]+@)?([A-Za-z0-9.-]+)", re.I)
PRIVATE_IP_RE = re.compile(
    r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01])|100\.(?:6[4-9]|[7-9]\d|1[01]\d|12[0-7]))\.\d{1,3}\.\d{1,3}\b"
)
HOME_RE = re.compile(r"(?:/home/|/Users/|C:\\Users\\)(?!user\b|me\b|runner\b|USERNAME\b|<)[A-Za-z0-9._-]+", re.I)
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
FORBIDDEN_FILES = re.compile(
    r"(^|/)(\.env|\.envrc|[^/]*\.(env|pem|key|p12|pfx|der|kdbx|session))$|(^|/)\.public-safety-denylist$"
)
ALLOWED_FILES = re.compile(r"\.env\.example$")
SELF = "scripts/check_public_safety.py"


def domain_allowed(host: str) -> bool:
    host = host.lower().rstrip(".")
    if host in {"127.0.0.1", "0.0.0.0"}:  # noqa: S104 - literal comparison
        return True
    if "." not in host:  # scheme-like tokens, single-label placeholders
        return True
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def is_placeholder_uuid(u: str) -> bool:
    hexs = u.replace("-", "").lower()
    return len(set(hexs)) == 1 or hexs.startswith("00000000")


def load_denylist() -> list[re.Pattern[str]]:
    lines: list[str] = []
    f = ROOT / ".public-safety-denylist"
    if f.is_file():
        lines += f.read_text().splitlines()
    lines += os.environ.get("PUBLIC_SAFETY_DENYLIST", "").splitlines()
    pats = []
    for ln in lines:
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            pats.append(re.compile(ln, re.I))
    return pats


def check_line(line: str, deny: list[re.Pattern[str]]) -> list[str]:
    if ALLOW_MARKER in line:
        return []
    problems = []
    for p in deny:
        if p.search(line):
            problems.append("matches private denylist entry")  # never echo the entry itself
            break
    for m in EMAIL_RE.finditer(line):
        if not domain_allowed(m.group(1)):
            problems.append(f"email with non-placeholder domain: {m.group(0)}")
    for m in URL_RE.finditer(line):
        if not domain_allowed(m.group(1)):
            problems.append(f"URL host not in allowlist: {m.group(1)}")
    for m in PRIVATE_IP_RE.finditer(line):
        problems.append(f"private IP address: {m.group(0)}")
    for m in HOME_RE.finditer(line):
        problems.append(f"personal home path: {m.group(0)}")
    for m in UUID_RE.finditer(line):
        if not is_placeholder_uuid(m.group(0)):
            problems.append(f"real-looking UUID (use 00000000-... placeholders): {m.group(0)}")
    return problems


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def check_files(paths: list[str], deny: list[re.Pattern[str]]) -> int:
    failures = 0
    for rel in paths:
        if FORBIDDEN_FILES.search(rel) and not ALLOWED_FILES.search(rel):
            print(f"{rel}: forbidden file type for a public repo (private config/key material)")
            failures += 1
            continue
        if rel == SELF:
            continue
        p = ROOT / rel
        if not p.is_file() or p.is_symlink():
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            for prob in check_line(line, deny):
                print(f"{rel}:{n}: {prob}")
                failures += 1
    return failures


def check_history(deny: list[re.Pattern[str]]) -> int:
    failures = 0
    try:
        log = git("log", "--all", "-p", "--no-color", "--no-ext-diff", "--format=@@COMMIT %H %ae %ce")
    except subprocess.CalledProcessError:
        print("not a git repository or no commits yet")
        return 0
    commit, current_file = "?", "?"
    for line in log.splitlines():
        if line.startswith("@@COMMIT "):
            _, commit, *emails = line.split(" ")
            for e in emails:
                dom = e.rsplit("@", 1)[-1]
                if any(p.search(e) for p in deny) or not (
                    domain_allowed(dom) or dom.endswith("users.noreply.github.com")
                ):
                    print(f"commit {commit[:10]}: author/committer email is not a public/noreply address")
                    failures += 1
            continue
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if FORBIDDEN_FILES.search(current_file) and not ALLOWED_FILES.search(current_file):
                print(f"commit {commit[:10]}: {current_file}: forbidden file type was committed")
                failures += 1
            continue
        if line.startswith("+") and not line.startswith("+++") and current_file != SELF:
            for prob in check_line(line[1:], deny):
                print(f"commit {commit[:10]}: {current_file}: {prob}")
                failures += 1
    return failures


def main(argv: list[str]) -> int:
    deny = load_denylist()
    if argv and argv[0] == "--history":
        failures = check_history(deny)
    elif argv and argv[0] == "--all":
        failures = check_files(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines(), deny)
    else:
        failures = check_files([os.path.relpath(Path(a).resolve(), ROOT) for a in argv], deny)
    if failures:
        print(
            f"\npublic-safety: {failures} problem(s). Replace with placeholders (example.com, "
            "00000000-... UUIDs, <your-value>) or mark a reviewed line with 'public-safety: allow'."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
