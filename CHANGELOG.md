# Changelog

## v0.2.1 (2026-10-09)

### Fix

- **bw-agent: authentication failures are now diagnosable** (#2). Previously
  `bw`'s own error output from login/unlock was discarded, so a failure only
  said "all authentication attempts failed" while `bw-agent doctor` reported
  OK.
  - `bw`'s output is printed under `bw reported:`, with secrets masked and
    repeated lines collapsed. It is also kept in
    `<cache>/<profile>.auth-error.log` (mode 600) until the next success.
  - Unlock is retried once before and once after the full re-login. This
    covers CLI/server combinations where the first unlock after login fails,
    e.g. `KeyIdBackfillError` / 404 on version skew.
  - `bw-agent doctor` now performs a real login/unlock (or validates the
    cached session) and reports `AUTH FAILED` with `bw`'s output instead of a
    configuration-only `OK`.
  - New `BW_AGENT_DEBUG=1` shows `bw`'s output even on success.
  - The Python tools return enough stderr for the detail to reach the model.

### CI

- Public-safety history check runs on the PR head commits instead of GitHub's
  synthetic merge commit, which carries the PR author's account email.
- Dependabot: bump `actions/checkout` to v7, `actions/setup-python` to v7 and
  `astral-sh/setup-uv` to v7 (#1).

### Fix

- **bw-agent**: surface bw's auth errors, retry unlock, real auth check in doctor

## v0.2.0 (2026-10-09)

First public release, published at
<https://github.com/oriolrius/skill-bitwarden>.

### Chore

- pre-commit: use the `ruff-check` hook id (the `ruff` alias is deprecated).
- Dependabot: Conventional Commits prefixes (`ci`, `chore(deps)`) and grouped
  updates, one PR per ecosystem.

### Verified

- CI passes on Ubuntu and macOS with Python 3.10 and 3.13: gitleaks and
  public-safety on the full history, shellcheck, ruff, skill validation, and
  the bats and pytest suites.
- End-to-end runs with a DeepSeek model through plain function calling,
  deepagents tools mode and deepagents skill mode (fake vault), and a
  read-only smoke test against a self-hosted server.

## v0.1.0 (2026-10-08)

### Feat

- `bw-agent`: non-interactive wrapper with API-key login, unlock via
  password command/file/env (never argv), session cache with locking,
  allowlisted mode-600 config file parsing, profiles, policy (blocked
  lifecycle commands, gated export, read-only mode) and `doctor`.
- Portable Agent Skill (`SKILL.md`, CLI and passkey references, passkey export script).
- Python package: client, secret redaction, OpenAI/DeepSeek tool specs and
  dispatcher, LangChain tools, deepagents helpers.
- Installer for Agent Skills harnesses (agents, deepagents, Claude Code, Codex, OpenCode).
- Guard rails: gitleaks (default + Bitwarden rules), public-safety check,
  pre-commit/pre-push hooks, GitHub Actions CI.

### Security hardening (from an internal review, before release)

- Read-only mode is an allowlist of read commands; options placed before the
  command are rejected, so `send -n list "text"` can't create a Send.
- Config values: inline ` # comments` are stripped and unrecognized flag
  values fail closed, so a commented line can't silently disable read-only.
- An inherited `BW_SESSION` is ignored (it used to trigger `bw logout`);
  `bw status` and the password command run without long-lived secrets.
- The lock is released before the user's command runs (flock fd closed;
  macOS `mkdir` lock removed and stale locks reclaimed).
- Python: `dispatch` never raises; `update_item` refuses identity keys
  (`id`, `organizationId`, `collectionIds`, …); text custom fields with
  secret-looking names are redacted.
- `SKILL.md` recipes pass secrets via environment variables, never `jq --arg`.
