# Changelog

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
