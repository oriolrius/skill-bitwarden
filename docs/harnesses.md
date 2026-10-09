# Harness integrations

All integrations share the same core (`bw-agent` + private config), so you
configure credentials once (`bw-agent doctor` must say `OK`) and then pick
one or more integrations.

## DeepSeek API — OpenAI-compatible function calling

DeepSeek's chat API accepts OpenAI-format `tools`. Install the package and
hand the specs to the model:

```bash
uv pip install "skill-bitwarden[openai] @ git+https://github.com/<you>/skill-bitwarden"
```

```python
from skill_bitwarden import AGENT_INSTRUCTIONS, dispatch, openai_tools

tools = openai_tools()  # list[{"type": "function", "function": {...}}]
result_json = dispatch(name, arguments_json)
```

- `dispatch` returns a JSON string and never raises. Errors come back as
  `{"error": ..., "detail": ...}` so the model can recover.
- Put `AGENT_INSTRUCTIONS` in the system prompt. It holds the sharing and
  least-exposure rules.
- With `BW_AGENT_READ_ONLY=1`, write tools are omitted automatically.
- To print the specs for other languages/harnesses:
  `uv run python -m skill_bitwarden tools-json`.
- The same code works against any OpenAI-compatible gateway (LiteLLM, vLLM,
  OpenRouter, …) via `base_url`.

Runnable: [`examples/deepseek_function_calling.py`](../examples/deepseek_function_calling.py).

### Tools

| Tool | Kind | Returns |
|---|---|---|
| `bitwarden_search` | read | metadata only: id, name, type, username, URIs, flags, custom field names |
| `bitwarden_get_item` | read | full item with secrets redacted |
| `bitwarden_get_secret` | read | one value: password / username / totp / notes / uri / custom field |
| `bitwarden_generate_password` | utility | random password or passphrase |
| `bitwarden_list_sends` | read | existing Sends |
| `bitwarden_sync` | utility | sync result |
| `bitwarden_create_send` | write | Send id + access URL |
| `bitwarden_create_login` | write | created item (redacted) |
| `bitwarden_update_item` | write | updated item (redacted) |

## LangChain Deep Agents (`deepagents`) — SDK

Works with any chat model. For DeepSeek, use `ChatOpenAI` with
`base_url="https://api.deepseek.com"` and `use_responses_api=False`:

```bash
uv pip install "skill-bitwarden[deepagents] @ git+https://github.com/<you>/skill-bitwarden"
```

```python
from skill_bitwarden.deepagents import create_bitwarden_agent

agent = create_bitwarden_agent(model)  # tools mode (recommended)
agent = create_bitwarden_agent(model, mode="skill")  # SKILL.md + LocalShellBackend
```

To compose it yourself:

```python
from deepagents import create_deep_agent
from skill_bitwarden import AGENT_INSTRUCTIONS
from skill_bitwarden.langchain import bitwarden_tools
from skill_bitwarden.deepagents import skill_source

agent = create_deep_agent(
    model=model,
    tools=[*my_tools, *bitwarden_tools()],
    system_prompt=MY_PROMPT + "\n\n" + AGENT_INSTRUCTIONS,
    interrupt_on={"bitwarden_create_send": True},
)  # human approval
# or, with a host-filesystem backend:
# create_deep_agent(..., backend=LocalShellBackend(virtual_mode=False, inherit_env=True),
#                   skills=[skill_source()])
```

Runnable: [`examples/deepagents_agent.py`](../examples/deepagents_agent.py).

## Deep Agents CLI

The CLI discovers skills on disk and gives the model a shell, so the skill
form is what it uses:

```bash
./install.sh --harness deepagents                 # ~/.deepagents/agent/skills/bitwarden
DEEPAGENTS_AGENT=myagent ./install.sh --harness deepagents
./install.sh --harness deepagents --scope project # ./.deepagents/skills/bitwarden
./install.sh --harness agents                     # ~/.agents/skills (shared by several harnesses)
```

## Agent Skills harnesses (Claude Code, Codex, OpenCode, …)

`skill/bitwarden/` follows the [Agent Skills](https://agentskills.io/specification)
layout: `SKILL.md` with `name`/`description` frontmatter, plus `scripts/` and
`references/`. It has no harness-specific syntax and no absolute paths.

```bash
./install.sh --harness claude [--scope project]
./install.sh --harness codex
./install.sh --harness opencode
./install.sh --target <any-skills-dir>
./install.sh --harness agents --link   # symlink for development
```

`./install.sh --bin` puts `bw-agent` on your `PATH` (`~/.local/bin`), so the
skill's short command form works in every harness.

## Shell, cron, CI

```bash
TOKEN="$(bw-agent get password "Example API token")"
BW_AGENT_PROFILE=ci BW_AGENT_NO_CACHE=1 bw-agent get notes "deploy key"
```

## Other languages / frameworks

The contract is just the CLI (`bw-agent <bw args>`, exit codes in
[configuration.md](configuration.md#exit-codes)) plus the JSON tool specs
(`python -m skill_bitwarden tools-json`). Any harness that can run a
subprocess can implement the same tools in a few lines.
