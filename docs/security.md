# Security model

Giving an LLM agent access to a password vault is inherently sensitive. This
project aims to keep the **blast radius small** and to make the safe path
the default one. It does not make an untrusted agent safe. Grant vault access
only to agents and environments you trust.

## Assets

- Master password, API key (`client_id`/`client_secret`), session key.
- Vault contents (passwords, TOTP seeds, notes, passkeys, attachments).
- Environment details (server URL, account, org/collection IDs) — sensitive
  for a public repository even though they are not secrets.

## Threats and mitigations

| Threat | Mitigation |
|---|---|
| Secrets visible in process lists / shell history | Master password passed via `--passwordenv`/`--passwordfile`. API key read from env by `bw login --apikey`. Session passed via `BW_SESSION` env. Item and Send payloads go through stdin in the Python layer. Tests assert no secret reaches any `bw` argv. |
| Child processes inheriting credentials | Every `bw` call gets only what it needs. `status` and the final command run without `BW_PASSWORD`, `BW_CLIENTSECRET` or `BW_CLIENTID`. `login` sees only the API key. `unlock` sees only a private password variable. `BW_PASSWORD_COMMAND` runs without the API key. A `BW_SESSION` inherited from the caller is ignored. |
| Config file abuse (code injection, `PATH`/`LD_PRELOAD` override) | The file is parsed, never sourced. Only schema keys are accepted. It must be owned by the user and mode 600. Unrecognized flag values fail closed. The only executed value is `BW_PASSWORD_COMMAND`, and `BW_BIN_DIR` chooses which `bw` runs; both are trusted because only the file's owner can write them. |
| Session key theft from disk | Cache dir 700, file 600, atomic writes. `BW_AGENT_NO_CACHE=1` disables it. The key is only valid while the vault stays unlocked on that machine. |
| Agent misusing the CLI (logout, server switch, full export) | Lifecycle commands (`login`, `logout`, `lock`, `unlock`, `config`, `serve`, `update`) and `--session` are blocked. `export` needs an explicit opt-in. A server mismatch aborts. |
| Agent changing the vault unexpectedly | `BW_AGENT_READ_ONLY=1` allows only an allowlist of read commands (`get`, `list`, `sync`, `send list/get/template/receive`, …). Options placed before the command are rejected so they can't confuse the check. The Python adapters also stop advertising write tools. The instructions require asking before writes. |
| Secrets flooding the LLM context / logs / provider | Search returns metadata only. `get_item` redacts passwords, TOTP, notes, password history, card/identity/SSH secrets, passkeys, attachment URLs, hidden custom fields, and text custom fields whose name looks secret (`token`, `key`, `secret`, …). The model must fetch one named field at a time. |
| Secrets shared in plain text by the agent | The skill instructions and `AGENT_INSTRUCTIONS` require Bitwarden Send (3 days, 3 accesses, hidden text by default) and only the link is shared. |
| Concurrent agents corrupting the session | Re-authentication is serialized by `flock` (or an atomic `mkdir` lock that reclaims stale locks). The cache is double-checked after acquiring the lock. The lock is released before the user's command runs. |
| Destructive recovery wiping shared CLI state | Recovery uses `bw logout` + re-login. Deleting the data dir needs `BW_HARD_RESET=1`. A missing `bw` fails fast before any recovery. |
| Personal / infrastructure data published in this repo | Gitleaks (default + Bitwarden rules) on history and tree in CI and pre-push. The public-safety check covers hostnames, emails, IPs, home paths, UUIDs, forbidden files and commit author emails, plus a private denylist. `.gitignore` covers config/key files. |

## Policy is a guard rail, not a sandbox

Read-only mode, the `export` gate and the blocked commands protect against
**mistakes** by a cooperative agent and keep tool-only agents within bounds.
They are **not** a security boundary against an agent that has a shell:

- Environment variables override the config file, so a shell-capable agent
  could run `BW_AGENT_READ_ONLY=0 bw-agent …` or call `bw` directly with the
  cached session key.
- The `export` gate blocks bulk dumps to a file, but `bw-agent list items`
  still returns every item including secrets. Restrict *what the account can
  see* (a dedicated account or organization collection) to bound exposure.

For a hard boundary, use **tools mode** (no shell) and give the agent a
Bitwarden account that only holds the items it needs.

## Residual risks

- **Anything the model sees can reach the model provider.** When the agent
  reads a secret, that secret is sent to whoever serves the model (DeepSeek or
  any other API) and may end up in logs/transcripts. Prefer flows where the
  secret goes straight to its destination (tool → file/env/Send) without
  passing through the conversation, and prefer self-hosted or zero-retention
  endpoints for sensitive vaults.
- **Prompt injection.** Content the agent reads (web pages, emails, vault
  notes) can try to trick it into exfiltrating secrets. Use read-only mode
  when writes aren't needed, limit which tools are exposed, and keep a human
  in the loop for sharing (deepagents `interrupt_on`, harness permission
  prompts).
- **Skill mode gives the model a shell.** With `mode="skill"` or a shell-based
  harness, the model can run arbitrary commands, including raw `bw` with the
  cached session key. Tools mode avoids this.
- A cached session key unlocks the vault for whoever can read it while it is
  valid. Use `BW_AGENT_NO_CACHE=1` on shared machines.
- `BW_PASSWORD_COMMAND` runs with your privileges. It is only read from your
  own environment or your own mode-600 file.

## Recommended setups

| Use case | Settings |
|---|---|
| Read-only lookup agent | `BW_AGENT_READ_ONLY=1`, tools mode, dedicated vault account or organization collection with only the needed items. |
| Ops agent that shares credentials | Tools mode, human approval on `bitwarden_create_send`, default Send limits. |
| Unattended automation (cron/CI) | Dedicated account, `BW_PASSWORD_FILE` from the platform's secret store, `BW_AGENT_NO_CACHE=1` on ephemeral runners. |
