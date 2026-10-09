# bw-agent configuration (for agents)

Agents normally do **not** configure anything — the human operator does once.
If a call fails with exit code 5 or 6, run `bw-agent doctor` and relay its
output to the user. Never ask the user to paste secrets into the chat; point
them to the config file instead.

## Where configuration comes from

1. Environment variables (highest precedence).
2. Private config file `${XDG_CONFIG_HOME:-~/.config}/bw-agent/<profile>.env`
   (`<profile>` = `$BW_AGENT_PROFILE`, default `default`; or `$BW_AGENT_CONFIG`).
   Must be owned by the user and mode `600`; it is parsed, never executed.

## Variables

| Variable | Purpose |
|---|---|
| `BW_SERVER` | Server base URL (cloud, self-hosted Bitwarden, Vaultwarden). Unset = keep the CLI's current server. |
| `BW_CLIENTID`, `BW_CLIENTSECRET` | Personal API key used by `bw login --apikey`. |
| `BW_PASSWORD_COMMAND` / `BW_PASSWORD_FILE` / `BW_PASSWORD` | Master-password source for unlock (one of them). |
| `BW_AGENT_READ_ONLY=1` | Block writes. |
| `BW_AGENT_ALLOW_EXPORT=1` | Allow `bw export`. |
| `BW_AGENT_NO_CACHE=1` | Don't store the session key on disk. |
| `BW_AGENT_PROFILE` | Select another account/server (separate config + cache). |
| `BITWARDENCLI_APPDATA_DIR` | Separate bw CLI state dir (needed per server). |
| `NODE_EXTRA_CA_CERTS` | Private CA bundle for self-hosted servers. |
| `BW_BIN_DIR` | Where `bw` lives if not on PATH. |

## Troubleshooting

| Symptom | Likely cause / fix (for the user) |
|---|---|
| exit 127 | Install the Bitwarden CLI or set `BW_BIN_DIR`. |
| exit 5 | API key or master-password source missing in the config. |
| exit 6 | Wrong API key / master password, or server unreachable. Check `bw-agent doctor`. |
| exit 4 | CLI state is logged in to another server: use a dedicated profile with its own `BITWARDENCLI_APPDATA_DIR`. |
| `invalid_client` that survives re-login | Corrupted CLI state; the user may run once with `BW_HARD_RESET=1`. |
| TLS errors on self-hosted | Set `NODE_EXTRA_CA_CERTS` to the CA bundle. |
