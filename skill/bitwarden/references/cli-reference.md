# Bitwarden CLI quick reference (via bw-agent)

Every command below is run as `bw-agent <args>`; the wrapper provides the
session. Official docs: <https://bitwarden.com/help/cli/>.

## Retrieve

```bash
bw-agent get password <id|term>
bw-agent get username <id|term>
bw-agent get totp <id|term>        # live code from the stored seed
bw-agent get notes <id|term>
bw-agent get uri <id|term>
bw-agent get item <id|term>        # full JSON (contains secrets!)
bw-agent get exposed <id|term>     # times the password appears in known breaches
bw-agent get folder <id> / get collection <id> / get organization <id>
bw-agent get attachment <filename> --itemid <id> --output /secure/path/
```

`<id|term>` is an exact GUID or a search term matching name/URI. Ambiguous
terms fail with "More than one result was found" — list, then use the id.

## Search and list

```bash
bw-agent list items --search "<term>"
bw-agent list items --url "https://example.com"
bw-agent list items --folderid <id>         # 'null' = no folder
bw-agent list items --collectionid <id>
bw-agent list items --organizationid <id>
bw-agent list items --trash
bw-agent list folders | list collections | list organizations
```

Filters combine with AND. Prefer projecting with jq so secrets don't hit the
conversation:

```bash
bw-agent list items --search "<term>" | jq '[.[] | {id, name, user: .login.username}]'
```

## Create / edit (JSON → `encode` → stdin)

```bash
bw-agent get template item            # also: item.login, item.field, folder, send.text
jq -n '{name:"My Folder"}' | bw-agent encode | bw-agent create folder
bw-agent get item <id> | jq '.name="New name"' | bw-agent encode | bw-agent edit item <id>
bw-agent create attachment --file ./file.txt --itemid <id>
bw-agent move <item-id> <organization-id>    # share item into an organization (pipe collection ids encoded)
```

Item types: `1` login, `2` secure note, `3` card, `4` identity, `5` SSH key.
Custom field types: `0` text, `1` hidden, `2` boolean, `3` linked.

## Delete / restore

```bash
bw-agent delete item <id>                 # to trash
bw-agent delete item <id> --permanent     # irreversible — explicit user request only
bw-agent restore item <id>
bw-agent delete attachment <attachment-id> --itemid <id>
```

## Generate

```bash
bw-agent generate                         # 14 chars, upper+lower+numbers
bw-agent generate -ulns --length 32
bw-agent generate --passphrase --words 5 --separator - --capitalize --includeNumber
```

## Send

```bash
bw-agent send template send.text
bw-agent send create            # reads base64 JSON from stdin
bw-agent send -f -n <name> -d <days> -a <max-access> <file> --fullObject
bw-agent send list | send get <id> | send delete <id>
bw-agent receive <url>          # read a Send someone shared with you
```

## Misc

```bash
bw-agent sync                     # pull latest data
bw-agent sync --last              # last sync timestamp
bw-agent status                   # server, user, lock state
bw-agent doctor                   # wrapper diagnostics (no secrets printed)
```

Output flags: `--pretty` (indented JSON), `--raw` (bare value),
`--response` (JSON envelope with success/error), `--nointeraction`.

`bw export` is blocked unless `BW_AGENT_ALLOW_EXPORT=1`.

## TOTP from a raw seed

When a TOTP seed is available but not stored in the vault (e.g. during
enrolment), compute the code locally — no network needed:

```bash
# Python (pyotp); run with your project's Python tooling, e.g. uv:
uv run --with pyotp python -c 'import os,pyotp; print(pyotp.TOTP(os.environ["SEED"]).now())'
# or oathtool, if installed:
oathtool --totp -b "$SEED"
```

Pass the seed through an environment variable, not a literal argument.
