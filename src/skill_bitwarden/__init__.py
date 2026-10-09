"""Portable, agent-friendly Bitwarden skill.

Core pieces:
    * ``skill/bitwarden`` — Agent Skill (SKILL.md + ``bw-agent`` wrapper), harness-neutral.
    * :class:`BitwardenClient` — Python client over the wrapper.
    * :mod:`skill_bitwarden.tools` — OpenAI/DeepSeek function-calling specs + dispatcher.
    * :mod:`skill_bitwarden.langchain` / :mod:`skill_bitwarden.deepagents` — adapters.
"""

from .client import BitwardenClient, BitwardenError, PolicyError
from .paths import skill_dir, skills_root, wrapper_path
from .redact import redact_item, summarize_item
from .tools import AGENT_INSTRUCTIONS, dispatch, openai_tools, tool_specs

__version__ = "0.2.0"

__all__ = [
    "AGENT_INSTRUCTIONS",
    "BitwardenClient",
    "BitwardenError",
    "PolicyError",
    "dispatch",
    "openai_tools",
    "redact_item",
    "skill_dir",
    "skills_root",
    "summarize_item",
    "tool_specs",
    "wrapper_path",
]
