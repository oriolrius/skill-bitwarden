# Security policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
private vulnerability reporting instead (*Security → Report a vulnerability* on
the repository page). Include steps to reproduce and the affected version.
You will get an acknowledgement within a few days.

Never include real credentials, vault exports, session keys or server URLs in
a report. Reproduce with placeholders or a throwaway vault.

## Supported versions

Only the latest release receives security fixes.

## Scope

In scope: the `bw-agent` wrapper, the Python package, the skill instructions
(e.g. guidance that could lead an agent to leak secrets), the installer and
the repository guard rails. Vulnerabilities in the Bitwarden CLI or server
themselves should be reported to Bitwarden / Vaultwarden.

The design and residual risks are described in [docs/security.md](docs/security.md).
