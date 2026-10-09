---
name: bitwarden
description: Access a Bitwarden or Vaultwarden password vault through the bw CLI using a non-interactive wrapper. Use to look up passwords, usernames, TOTP codes, notes or custom fields; search the vault; create or edit items; generate passwords; and share credentials safely through expiring Bitwarden Send links. Triggers include "get password", "credentials for", "API key for", "TOTP", "2FA code", "generate password", "share/send credentials", "bitwarden", "vaultwarden", "vault", "bw".
license: MIT
compatibility: Requires bash, the Bitwarden CLI (bw) and jq. Configuration is read from the environment or a private config file; see references/configuration.md.
---

# Bitwarden vault access

All vault access goes through **`bw-agent`**, a wrapper around the official `bw`
CLI. It loads private configuration, logs in, unlocks, caches the session and
then runs the `bw` subcommand you give it. **One call, no interactive prompts.**

## Locating the wrapper

The wrapper is `scripts/bw-agent` inside this skill's directory (the folder
containing this `SKILL.md`). Use whichever works:

```bash
bw-agent <bw args...>                       # if installed on PATH
bash <skill-dir>/scripts/bw-agent <bw args...>   # always works
```

Below, `bw-agent` stands for either form. Use absolute paths.

## Rules

1. **Never run raw `bw`**, and never run `bw login`, `bw logout`, `bw unlock`,
   `bw lock` or `bw config` — the wrapper manages the session and blocks them.
2. **Never put secrets on a command line** you build (they leak via shell
   history and process lists) — not even as `jq --arg`. Pass them through
   environment variables (`jq ... '$ENV.VAR'`) or stdin, as shown below.
3. **Fetch only what you need.** Search first, then get the single field.
   Don't dump full items or the whole vault into the conversation.
4. **Never share secrets in plain text** (email, chat, tickets, commits,
   docs). Create a Bitwarden Send and share only its link (see *Sharing*).
5. **Ask before** creating, editing or deleting items.
6. First run or auth errors → run `bw-agent doctor` and report what it says.
   Do not try to fix credentials yourself.

## Retrieve

```bash
bw-agent get password "<item name, domain or id>"
bw-agent get username "<item>"
bw-agent get totp "<item>"          # current one-time code
bw-agent get notes "<item>"
bw-agent get item "<id>" | jq '.fields[] | select(.name=="<field>") | .value' -r
```

`get` fails with "More than one result was found" when the term is ambiguous:
search, then use the item **id**.

## Search (metadata only)

```bash
bw-agent list items --search "<term>" \
  | jq '[.[] | {id, name, username: .login.username, uri: .login.uris[0].uri}]'
bw-agent list items --url "https://app.example.com" | jq '[.[] | {id, name}]'
```

## Create a login

```bash
PASS="$(bw-agent generate -ulns --length 24)" \
jq -n --arg name "<Service name>" --arg user "<username>" --arg uri "<https://...>" \
  '{type:1, name:$name, notes:null, favorite:false, fields:[], reprompt:0,
    organizationId:null, collectionIds:null, folderId:null,
    login:{username:$user, password:$ENV.PASS, totp:null, uris:[{match:null, uri:$uri}]}}' \
  | bw-agent encode | bw-agent create item | jq '{id, name}'
```

To store a password the user gave you, put it in the variable the same way
(`PASS='...'` prefix), never in `--arg`.

## Edit / delete / restore

```bash
ID=$(bw-agent get item "<item>" | jq -r .id)
bw-agent get item "$ID" | NEW='<new value>' jq '.login.password = $ENV.NEW' \
  | bw-agent encode | bw-agent edit item "$ID" | jq '{id, name}'
bw-agent delete item "$ID"                 # to trash (restorable)
bw-agent restore item "$ID"
```

Permanent deletion (`--permanent`) only on explicit user request.

## Generate

```bash
bw-agent generate -ulns --length 24          # upper, lower, numbers, special
bw-agent generate --passphrase --words 5 --separator -
```

## Sharing credentials — Bitwarden Send

When asked to send/share credentials with someone, **always**:

1. Create a Send containing the secret.
2. Share **only the link** through the requested channel.
3. Report back: recipient, link, expiry and max accesses.

Defaults unless the user says otherwise: expires in **3 days**, **3** max
accesses, text **hidden**. Pass the secret text through an environment
variable (real newlines survive, nothing lands in argv):

```bash
DELETION=$(date -u -d '+3 days' +%Y-%m-%dT%H:%M:%S.000Z 2>/dev/null \
        || date -u -v+3d +%Y-%m-%dT%H:%M:%S.000Z)          # GNU || BSD date
export SEND_TEXT='<secret text, may span lines>'
bw-agent send template send.text \
  | jq --arg name "<label>" --arg del "$DELETION" \
       '.name=$name | .text.text=$ENV.SEND_TEXT | .text.hidden=true | .maxAccessCount=3 | .deletionDate=$del' \
  | bw-agent encode | bw-agent send create \
  | jq '{id, accessUrl, deletionDate, maxAccessCount}'
unset SEND_TEXT
```

Files: `bw-agent send -f -n "<label>" -d 3 -a 3 /path/to/file --fullObject | jq '{accessUrl}'`.
List: `bw-agent send list | jq '.[] | {id, name, accessUrl, deletionDate, accessCount}'`.
Revoke: `bw-agent send delete <id>`.

## Other operations

- Passkeys (FIDO2) export to PEM: `scripts/bw-passkey-export <item-id> [dir]`
  — see `references/passkeys.md`. Output is raw private keys: shred after use.
- TOTP from a raw seed (no vault item): see `references/cli-reference.md`.
- Full CLI cheat sheet: `references/cli-reference.md`.
- Configuration and troubleshooting: `references/configuration.md`.

## Exit codes from bw-agent

| code | meaning |
|------|---------|
| 2 | command blocked by policy (lifecycle command, `export`, `--session`, options before the command) |
| 3 | blocked by read-only mode |
| 4 | CLI is logged in to a different server than configured |
| 5 | configuration missing (API key / master password source) |
| 6 | authentication failed |
| 127 | `bw` CLI not found |

Anything else is the exit code of `bw` itself.
