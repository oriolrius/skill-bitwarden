"""Integration helpers for LangChain Deep Agents (``deepagents``).

Two integration styles are supported:

* **tools** (recommended for SDK agents): the model gets typed
  ``bitwarden_*`` tools; no shell access is required, secrets are redacted by
  default and policy is enforced by the wrapper.
* **skill**: the portable ``SKILL.md`` is exposed through the deepagents skills
  system and the model runs ``bw-agent`` through the shell ``execute`` tool.
  Use this when the agent already has a shell backend (e.g. deepagents CLI).

Works with any chat model, e.g. DeepSeek via its OpenAI-compatible API::

    from langchain_openai import ChatOpenAI
    from skill_bitwarden.deepagents import create_bitwarden_agent

    model = ChatOpenAI(model="deepseek-chat", base_url="https://api.deepseek.com", api_key=...)
    agent = create_bitwarden_agent(model)
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Literal

from .client import BitwardenClient
from .paths import skills_root
from .tools import AGENT_INSTRUCTIONS


def skill_source(label: str = "Bitwarden") -> tuple[str, str]:
    """A deepagents skill source ``(path, label)`` for ``create_deep_agent(skills=[...])``.

    The path is a real filesystem path, so pair it with a backend that reads
    the host filesystem (``FilesystemBackend``/``LocalShellBackend`` with
    ``virtual_mode=False``).
    """
    return (str(skills_root()) + "/", label)


def create_bitwarden_agent(
    model: Any,
    *,
    mode: Literal["tools", "skill"] = "tools",
    tools: Sequence[Any] = (),
    system_prompt: str | None = None,
    client: BitwardenClient | None = None,
    read_only: bool | None = None,
    **kwargs: Any,
) -> Any:
    """Build a deep agent with Bitwarden access.

    Extra ``kwargs`` are forwarded to ``deepagents.create_deep_agent``.
    """
    from deepagents import create_deep_agent

    prompt = "\n\n".join(p for p in (system_prompt, AGENT_INSTRUCTIONS) if p)
    if mode == "tools":
        from .langchain import bitwarden_tools

        all_tools = [*tools, *bitwarden_tools(client, read_only)]
        return create_deep_agent(model=model, tools=all_tools, system_prompt=prompt, **kwargs)

    if mode == "skill":
        from deepagents.backends import LocalShellBackend

        backend = kwargs.pop("backend", None) or LocalShellBackend(virtual_mode=False, inherit_env=True)
        skills = [*kwargs.pop("skills", []), skill_source()]
        return create_deep_agent(
            model=model, tools=list(tools), system_prompt=prompt, backend=backend, skills=skills, **kwargs
        )

    raise ValueError("mode must be 'tools' or 'skill'")
