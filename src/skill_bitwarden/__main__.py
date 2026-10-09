"""Small CLI: ``python -m skill_bitwarden <command>``.

skill-dir     print the directory containing SKILL.md
wrapper       print the path to bw-agent
tools-json    print the OpenAI/DeepSeek tool specs (respects BW_AGENT_READ_ONLY)
call NAME [JSON_ARGS]   run one tool call and print its JSON result
"""

from __future__ import annotations

import json
import sys

from .paths import skill_dir, wrapper_path
from .tools import dispatch, openai_tools


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    cmd = args[0] if args else "help"
    if cmd == "skill-dir":
        print(skill_dir())
    elif cmd == "wrapper":
        print(wrapper_path())
    elif cmd == "tools-json":
        print(json.dumps(openai_tools(), indent=2))
    elif cmd == "call" and len(args) >= 2:
        result = dispatch(args[1], args[2] if len(args) > 2 else "{}")
        print(result)
        return 1 if '"error"' in result[:12] else 0
    else:
        print(__doc__)
        return 0 if cmd in ("help", "-h", "--help") else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
