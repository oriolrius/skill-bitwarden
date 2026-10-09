# skill-bitwarden

A portable, security-first **Bitwarden / Vaultwarden skill for AI agents**.
It gives an agent safe, non-interactive access to a password vault: look up
credentials, TOTP codes and custom fields, create or update items, generate
passwords, and share secrets through expiring **Bitwarden Send** links rather
than in plain text.

It works with any Bitwarden-compatible server (Bitwarden cloud US/EU,
self-hosted Bitwarden, Vaultwarden). The repository holds no server URL,
account, organization or collection IDs. You supply all of that locally.

| Harness | Integration |
|---|---|
| **DeepSeek** API (and any OpenAI-compatible endpoint) | `openai_tools()` + `dispatch()` function-calling tools |
| **LangChain Deep Agents** (`deepagents` SDK/CLI), e.g. on DeepSeek models | typed tools (`create_bitwarden_agent`) or the `SKILL.md` skill |
| Any LangChain / LangGraph agent | `skill_bitwarden.langchain.bitwarden_tools()` |
| Agent Skills harnesses (Claude Code, Codex, OpenCode, …) | `skill/bitwarden/` (`SKILL.md` + scripts) |
| Plain shell / cron / CI | the `bw-agent` wrapper |

## How it fits together

```
 ┌──────────────── public, reusable (this repo) ────────────────┐
 │ skill/bitwarden/SKILL.md      agent instructions (harness-neutral)
 │ skill/bitwarden/scripts/bw-agent   auth + session cache + policy → bw CLI
 │ src/skill_bitwarden/          Python client, redaction, tool specs,
 │                               LangChain + deepagents adapters
 │ config/schema.json            public configuration schema
 │ config/bw-agent.env.example   placeholder template
 └──────────────────────────────────────────────────────────────┘
 ┌──────────────── private, local only (never committed) ───────┐
 │ ~/.config/bw-agent/<profile>.env   (mode 600) or environment vars
 │ ~/.cache/bw-agent/<profile>.session (mode 600) session key cache
 └──────────────────────────────────────────────────────────────┘
```

Every path ends up at **`bw-agent`**, a single-shot wrapper around the
official Bitwarden CLI. It:

- loads configuration from the environment, then a private mode-600 file. The
  file is **parsed, never sourced**, and only allowlisted keys are accepted.
  The one value ever executed is your own `BW_PASSWORD_COMMAND`, by design;
- logs in with a personal **API key** and unlocks with the master password. The
  password comes from a password command (keyring/`pass`), a file, or an env
  var, and is passed via `--passwordenv`/`--passwordfile`. **Secrets never
  appear on a command line**;
- caches the session key (mode 600) and serializes re-authentication across
  concurrent agents with a lock;
- enforces policy: it blocks `login`/`logout`/`unlock`/`lock`/`config`/`serve`/`update`
  and `--session`, gates `export`, and has an optional allowlist-based
  **read-only mode**. These are guard rails against agent mistakes, not a
  sandbox (see [docs/security.md](docs/security.md));
- recovers from auth faults without wiping shared CLI state (wiping is opt-in).

The Python layer adds **least-exposure tools**. Search results and item views
are **redacted**, and the model fetches exactly one secret at a time.
Send/item payloads go through stdin.

## Quick start

### 1. Prerequisites

- `bash`, `jq`, and the [Bitwarden CLI](https://bitwarden.com/help/cli/)
  (`npm install -g @bitwarden/cli`, `brew install bitwarden-cli`, `snap install bw`,
  or the native binary).
- A personal API key: Web vault → *Account settings → Security → Keys → View API key*.
- Python ≥ 3.10 and [uv](https://docs.astral.sh/uv/), only for the Python
  tools/adapters (deepagents needs ≥ 3.11).

### 2. Install the skill and create your private config

```bash
git clone https://github.com/<you>/skill-bitwarden.git && cd skill-bitwarden
./install.sh --init-config --bin          # ~/.config/bw-agent/default.env (600) + bw-agent on PATH
$EDITOR ~/.config/bw-agent/default.env    # fill in server, API key, password source
bw-agent doctor                           # validates config, never prints secrets
bw-agent list items --search example | jq '.[].name'
```

### 3. Wire it into your harness

```bash
./install.sh --harness deepagents         # ~/.deepagents/agent/skills/bitwarden
./install.sh --harness agents             # ~/.agents/skills (shared Agent Skills dir)
./install.sh --harness claude --scope project
./install.sh --target /path/to/any/skills/dir
```

**DeepSeek function calling** (no framework):

```python
from openai import OpenAI
from skill_bitwarden import AGENT_INSTRUCTIONS, dispatch, openai_tools

client = OpenAI(api_key=..., base_url="https://api.deepseek.com")
resp = client.chat.completions.create(
    model="deepseek-chat", tools=openai_tools(), messages=[{"role": "system", "content": AGENT_INSTRUCTIONS}, ...]
)
for call in resp.choices[0].message.tool_calls or []:
    result_json = dispatch(call.function.name, call.function.arguments)
```

**Deep Agents on DeepSeek:**

```python
from langchain_openai import ChatOpenAI
from skill_bitwarden.deepagents import create_bitwarden_agent

model = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com", api_key=..., use_responses_api=False)
agent = create_bitwarden_agent(model)  # mode="skill" to use SKILL.md + shell
```

Full runnable versions are in [`examples/`](examples/). Per-harness details are in
[`docs/harnesses.md`](docs/harnesses.md).

## Configuration

Variables come from the environment or `~/.config/bw-agent/<profile>.env`.
The environment takes precedence. The full reference is
[`docs/configuration.md`](docs/configuration.md), and the machine-readable
schema is [`config/schema.json`](config/schema.json).

| Variable | Required | Purpose |
|---|---|---|
| `BW_SERVER` | – | Server URL; unset keeps the CLI's current server |
| `BW_CLIENTID` / `BW_CLIENTSECRET` | ✓ | Personal API key |
| `BW_PASSWORD_COMMAND` \| `BW_PASSWORD_FILE` \| `BW_PASSWORD` | ✓ (one) | Master-password source |
| `BW_AGENT_PROFILE` | – | Switch account/server (separate config + cache) |
| `BW_AGENT_READ_ONLY` | – | `1` blocks all writes (tools are hidden too) |
| `BW_AGENT_ALLOW_EXPORT` | – | `1` allows `bw export` |
| `BW_AGENT_NO_CACHE` | – | `1` never writes the session key to disk |

## Security

- The threat model and design decisions are in [`docs/security.md`](docs/security.md).
  Vulnerability reporting is covered in [`SECURITY.md`](SECURITY.md).
- **Repository guard rails:**
  - Gitleaks runs in CI on the full history and on the working tree. It uses
    the default rules plus Bitwarden-specific ones (API client id/secret,
    master password, session key).
  - A **public-safety check** blocks real hostnames, emails, private IPs, home
    paths, real-looking UUIDs and committed config files. It can also read a
    private denylist kept outside the repo.
  - Pre-commit / pre-push hooks run the same checks locally.

## Development

```bash
uv sync                                       # dev environment
uv run pre-commit install                     # pre-commit + pre-push hooks
make check                                    # lint + tests + secret/public-safety scans
```

Tests run against a **fake `bw` CLI** (`tests/fixtures/fake-bw`), so they never
need a real vault or network. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## License

[MIT](LICENSE)
