"""LangChain Deep Agents + DeepSeek with Bitwarden access.

    uv sync --extra deepagents
    export DEEPSEEK_API_KEY=...            # see examples/.env.example
    uv run python examples/deepagents_agent.py "Share the Example Service password with alice@example.com"
    uv run python examples/deepagents_agent.py --mode skill "What's the username for Example Service?"

--mode tools  (default) typed bitwarden_* tools; no shell access needed.
--mode skill  loads SKILL.md through the deepagents skills system and lets the
              model run bw-agent via the shell `execute` tool (gives the model a
              local shell — only use where that is acceptable).
"""

from __future__ import annotations

import argparse
import os
import uuid

from langchain_openai import ChatOpenAI

from skill_bitwarden.deepagents import create_bitwarden_agent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("prompt", nargs="+")
    ap.add_argument("--mode", choices=["tools", "skill"], default="tools")
    args = ap.parse_args()

    model = ChatOpenAI(
        model=os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        api_key=os.environ["DEEPSEEK_API_KEY"],
        temperature=0,
        use_responses_api=False,  # DeepSeek and most gateways speak chat-completions only
    )
    agent = create_bitwarden_agent(model, mode=args.mode)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": " ".join(args.prompt)}]},
        config={"configurable": {"thread_id": str(uuid.uuid4())}, "recursion_limit": 50},
    )
    print(result["messages"][-1].content)


if __name__ == "__main__":
    main()
