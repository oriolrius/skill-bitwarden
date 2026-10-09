# Configuration

Configuration has three layers, kept strictly apart:

| Layer | Where | Committed? |
|---|---|---|
| Skill logic | `skill/bitwarden/`, `src/skill_bitwarden/` | yes |
| Public schema & templates | `config/schema.json`, `config/bw-agent.env.example`, `examples/.env.example` | yes (placeholders only) |
| Private config & credentials | environment variables, `~/.config/bw-agent/<profile>.env`, session cache | **never** |

## Resolution order

1. **Environment variables** win.
2. **Config file** `${XDG_CONFIG_HOME:-~/.config}/bw-agent/<profile>.env`.
   The profile comes from `BW_AGENT_PROFILE` (default `default`); `BW_AGENT_CONFIG`
   overrides the path.
3. Built-in defaults (see below). There is **no default server**. If
   `BW_SERVER` is unset, the server already configured in the bw CLI data dir
   is used (the Bitwarden cloud on a fresh install).

A `BW_SESSION` exported by the caller is ignored, because the wrapper manages
its own session.

### Config file rules

- It must be a regular file **owned by you** with **no group/other
  permissions** (`chmod 600`). Otherwise bw-agent refuses to run. The escape
  hatch `BW_AGENT_ALLOW_INSECURE_CONFIG=1` is discouraged.
- Format is `KEY=VALUE`, one per line. `#` comment lines, inline comments
  (` # …` after an unquoted value), a leading `export`, and surrounding
  `'…'`/`"…"` quotes are accepted. Quote values that contain ` #`.
- Flag values must be `0`/`1` (or `true`/`false`, `yes`/`no`, `on`/`off`).
  Anything else is an error. A typo never silently disables read-only mode.
- It is **parsed, not sourced**. `$(…)`, backticks and `${…}` are kept as
  literal text and never executed.
- Only keys from the schema are accepted. Anything else (`PATH`,
  `LD_PRELOAD`, …) is ignored with a warning.

## Variables

### Connection & credentials

| Variable | Secret | Description |
|---|---|---|
| `BW_SERVER` | no | Base URL of the server, e.g. `https://vault.example.com`, the Bitwarden US/EU cloud, or Vaultwarden. |
| `BW_CLIENTID` | yes | API key `client_id` (`user.<uuid>`). |
| `BW_CLIENTSECRET` | yes | API key `client_secret`. |
| `BW_PASSWORD_COMMAND` | no | Command printing the master password (first line used). Recommended. |
| `BW_PASSWORD_FILE` | no | File whose first line is the master password (keep it mode 600). |
| `BW_PASSWORD` | yes | Master password as a plain value. Simplest, least safe. |

The master-password sources are tried in the order `BW_PASSWORD`,
`BW_PASSWORD_FILE`, `BW_PASSWORD_COMMAND`. Set exactly one.

Examples of `BW_PASSWORD_COMMAND`:

```bash
BW_PASSWORD_COMMAND=secret-tool lookup service bitwarden account default    # GNOME keyring / libsecret
BW_PASSWORD_COMMAND=security find-generic-password -s bitwarden -w          # macOS Keychain
BW_PASSWORD_COMMAND=pass show bitwarden/master                              # pass
BW_PASSWORD_COMMAND=op read op://Private/bitwarden/password                 # another manager's CLI
```

### Behaviour & policy

| Variable | Default | Description |
|---|---|---|
| `BW_AGENT_READ_ONLY` | `0` | `1` allows only read commands: `get`, `list`, `sync`, `generate`, `encode`, `status`, `completion`, `help`, `receive`, `sdk-version`, and `send list/get/template/receive`. Everything else (create, edit, delete, restore, move, import, confirm, share, device-approval, creating Sends, …) is blocked. Python adapters also stop advertising write tools. |
| `BW_AGENT_ALLOW_EXPORT` | `0` | `1` allows `bw export`. |
| `BW_AGENT_NO_CACHE` | `0` | `1` keeps the session key off disk (unlock on every call). |
| `BW_AGENT_CACHE_DIR` | `${XDG_CACHE_HOME:-~/.cache}/bw-agent` | Session cache + lock directory (created mode 700). |
| `BW_AGENT_LOCK_TIMEOUT` | `60` | Seconds to wait for the re-authentication lock. |
| `BW_AGENT_DEBUG` | `0` | `1` prints the bw CLI's login/unlock output (secrets masked) even on success. On failure it is always printed. |
| `BW_HARD_RESET` | `0` | `1` lets recovery delete the bw CLI data dir. Only for on-disk corruption. |

### Environment-only selectors

| Variable | Description |
|---|---|
| `BW_AGENT_PROFILE` | Profile name (`[A-Za-z0-9._-]+`). Selects the config file and the session cache. |
| `BW_AGENT_CONFIG` | Explicit config file path. |
| `BW_AGENT_ALLOW_INSECURE_CONFIG` | Accept a group/world-readable config file. |
| `BW_AGENT_BIN` | (Python) explicit path to `bw-agent`. |
| `BW_AGENT_TIMEOUT` | (Python) per-call timeout in seconds, default 120. |

### Native variables passed through

| Variable | Description |
|---|---|
| `BITWARDENCLI_APPDATA_DIR` | bw CLI state dir. **Use one per server/account.** |
| `NODE_EXTRA_CA_CERTS` | Extra CA bundle (PEM) for self-hosted servers behind a private CA. |
| `BW_BIN_DIR` | Directory that contains `bw` (and `node` for the npm build) when it is not on `PATH`, e.g. under cron/systemd. |

## Multiple servers / accounts

The bw CLI keeps login state in a single data dir. To use several
servers/accounts, give each its own profile **and** its own data dir:

```bash
# ~/.config/bw-agent/work.env  (mode 600)
BW_SERVER=https://vault.work.example.com
BW_CLIENTID=user.00000000-0000-0000-0000-000000000000
BW_CLIENTSECRET=<secret>
BW_PASSWORD_COMMAND=secret-tool lookup service bitwarden account work
BITWARDENCLI_APPDATA_DIR=/home/user/.local/share/bw-agent/work
```

```bash
BW_AGENT_PROFILE=work bw-agent get password "example"
```

If the CLI state is logged in to a different server than `BW_SERVER`,
bw-agent stops with exit code 4. It won't silently switch servers.

## Running under cron / systemd

Minimal environments often lack the directory where `bw` lives. bw-agent looks
in `PATH`, then `BW_BIN_DIR`, the newest `~/.nvm/versions/node/*/bin`,
`~/.local/bin`, `/usr/local/bin`, `/opt/homebrew/bin`, `/usr/bin` and
`/snap/bin`. Set `BW_BIN_DIR` if it is somewhere else.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | success (or the `bw` exit code) |
| 1 | generic wrapper error (e.g. unsafe config file) |
| 2 | command blocked by policy |
| 3 | blocked by read-only mode |
| 4 | server mismatch with the CLI state |
| 5 | missing configuration |
| 6 | authentication failed. `bw`'s own error output is printed (secrets masked) and kept in `<cache>/<profile>.auth-error.log` until the next success |
| 127 | `bw` not found |
