"""LangChain adapter (used by deepagents and any LangChain/LangGraph agent).

Requires the ``langchain`` extra: ``uv pip install 'skill-bitwarden[langchain]'``.
"""

from __future__ import annotations

from typing import Any

from .client import BitwardenClient
from .tools import dispatch, tool_specs


def bitwarden_tools(client: BitwardenClient | None = None, read_only: bool | None = None) -> list[Any]:
    """Return the Bitwarden tools as LangChain ``StructuredTool`` objects."""
    try:
        from langchain_core.tools import StructuredTool
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError("install the 'langchain' extra: skill-bitwarden[langchain]") from exc

    c = client or BitwardenClient()
    tools = []
    for spec in tool_specs(read_only, c):
        name = spec["name"]

        def _run(_name: str = name, **kwargs: Any) -> str:
            return dispatch(_name, {k: v for k, v in kwargs.items() if v is not None}, client=c)

        tools.append(
            StructuredTool.from_function(
                func=_run,
                name=name,
                description=spec["description"],
                args_schema=spec["parameters"],
            )
        )
    return tools
