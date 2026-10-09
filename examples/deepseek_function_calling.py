"""Minimal DeepSeek (OpenAI-compatible) tool-calling loop with the Bitwarden tools.

No agent framework needed: the tool specs are plain OpenAI ``tools`` JSON and
``dispatch`` executes a call through bw-agent.

    uv sync --extra openai
    export DEEPSEEK_API_KEY=...            # see examples/.env.example
    uv run python examples/deepseek_function_calling.py "What is the username for Example Service?"

Works against any OpenAI-compatible endpoint (a LiteLLM/vLLM gateway, etc.) by
setting DEEPSEEK_BASE_URL / DEEPSEEK_MODEL.
"""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI

from skill_bitwarden import AGENT_INSTRUCTIONS, dispatch, openai_tools

MAX_STEPS = 8


def main() -> int:
    question = " ".join(sys.argv[1:]) or "Search the vault for 'example' and list item names."
    client = OpenAI(
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")
    messages: list[dict] = [
        {"role": "system", "content": AGENT_INSTRUCTIONS},
        {"role": "user", "content": question},
    ]
    tools = openai_tools()
    for _ in range(MAX_STEPS):
        resp = client.chat.completions.create(model=model, messages=messages, tools=tools)
        msg = resp.choices[0].message
        messages.append(msg.model_dump(exclude_none=True))
        if not msg.tool_calls:
            print(msg.content)
            return 0
        for call in msg.tool_calls:
            result = dispatch(call.function.name, call.function.arguments)
            print(f"[tool] {call.function.name}({call.function.arguments}) -> {len(result)} bytes", file=sys.stderr)
            messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
    print("stopped after max steps", file=sys.stderr)
    print(json.dumps(messages[-1], indent=2, default=str))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
