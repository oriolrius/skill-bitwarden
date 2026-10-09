# Changelog

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
