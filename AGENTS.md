# AGENTS.md — working on skill-bitwarden

Instructions for coding agents contributing to this repository.

- This is a **public** repository. Never write real credentials, server URLs,
  hostnames, emails, IPs, Bitwarden item/org/collection IDs or personal paths
  into any file, test, example or commit message. Use `example.com`,
  `00000000-…` UUIDs and `<placeholder>` values.
- Layout: `skill/bitwarden/` is the harness-neutral Agent Skill (keep it free of
  harness-specific syntax and absolute paths). `src/skill_bitwarden/` is the
  Python layer. `config/` holds the public schema and template. Private config
  lives only in `~/.config/bw-agent/` or the environment.
- Auth, config parsing and policy live **only** in
  `skill/bitwarden/scripts/bw-agent`. The Python layer shells out to it and
  must not duplicate that logic.
- Never pass secrets on a command line. Use stdin or environment variables.
- Tests use the fake CLI in `tests/fixtures/fake-bw/bw`. Never point tests at a
  real vault.
- Before finishing, run `make check` (shellcheck, ruff, skill validation,
  bats, pytest, gitleaks, public-safety).
- Python tooling: use `uv` (`uv sync`, `uv run …`).
