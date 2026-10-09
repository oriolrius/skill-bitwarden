# Contributing

## Ground rules (public repository)

- **No real data, ever.** No credentials, tokens, server URLs, hostnames,
  emails, IPs, organization/collection/item IDs or personal paths. Use
  `example.com` / `example.org`, `00000000-0000-0000-0000-000000000000`-style
  UUIDs and `<your-value>` placeholders.
- Commit with a public or `@users.noreply.github.com` email. The CI history
  check rejects other author/committer emails.
- Keep the skill harness-neutral: no harness-specific syntax or absolute paths
  in `skill/bitwarden/`.

## Setup

```bash
uv sync                                             # Python dev environment
uv run pre-commit install                           # pre-commit + pre-push hooks
cp /dev/null .public-safety-denylist && chmod 600 .public-safety-denylist
$EDITOR .public-safety-denylist                     # optional: your private strings (gitignored)
```

Requirements: `bash`, `jq`, `bats`, `shellcheck`, `gitleaks`.

## Checks

```bash
make check        # everything CI runs
make test         # bats + pytest (fake bw CLI, no network)
make scan         # gitleaks (history + tree) + public-safety (tree + history)
```

## Changes to configuration

A new configuration key must be added in **all** of:
`ALLOWED_KEYS` in `skill/bitwarden/scripts/bw-agent`, `config/schema.json`,
`docs/configuration.md` and, if useful, `config/bw-agent.env.example`. A test
enforces that the wrapper and the schema agree.

## Commits & releases

Conventional Commits (`feat:`, `fix:`, `docs:` …). Versions are bumped with
commitizen (`uvx --from commitizen cz bump`), which updates `pyproject.toml`,
the package and the wrapper versions and `CHANGELOG.md`.
