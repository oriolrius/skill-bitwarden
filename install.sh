#!/usr/bin/env bash
# Install the Bitwarden skill into one or more agent harnesses.
#
#   ./install.sh --harness deepagents            # copy into ~/.deepagents/agent/skills/bitwarden
#   ./install.sh --harness claude --scope project
#   ./install.sh --target /custom/skills/dir     # any harness that reads Agent Skills
#   ./install.sh --harness agents --link         # symlink (for development)
#   ./install.sh --init-config                   # create the private config template (mode 600)
#   ./install.sh --bin                           # put bw-agent on PATH (~/.local/bin)
#
# Options may be combined. Nothing outside the chosen targets is modified and
# existing private configuration is never overwritten.

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/skill/bitwarden"
SCOPE=user
LINK=0
FORCE=0
TARGETS=()
DO_CONFIG=0
DO_BIN=0
BIN_DIR="${BIN_DIR:-$HOME/.local/bin}"
DEEPAGENTS_AGENT="${DEEPAGENTS_AGENT:-agent}"

usage() { sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'; cat <<'EOF'

Harnesses (--harness, repeatable):
  agents      shared Agent Skills dir   user: ~/.agents/skills            project: ./.agents/skills
  deepagents  LangChain Deep Agents CLI user: ~/.deepagents/$DEEPAGENTS_AGENT/skills
                                         project: ./.deepagents/skills
  claude      Claude Code               user: ~/.claude/skills            project: ./.claude/skills
  codex       OpenAI Codex CLI          user: ~/.codex/skills             project: ./.codex/skills
  opencode    OpenCode                  user: ~/.config/opencode/skills   project: ./.opencode/skills

Other options:
  --scope user|project   (default: user; project = current directory)
  --target DIR           install into DIR/bitwarden (repeatable)
  --link                 symlink instead of copy
  --force                replace an existing installation
  --init-config          create ${XDG_CONFIG_HOME:-~/.config}/bw-agent/default.env from the template
  --bin                  symlink bw-agent into $BIN_DIR
EOF
}

harness_dir() {
    local h="$1"
    if [ "$SCOPE" = user ]; then
        case "$h" in
            agents) echo "$HOME/.agents/skills" ;;
            deepagents) echo "$HOME/.deepagents/$DEEPAGENTS_AGENT/skills" ;;
            claude) echo "$HOME/.claude/skills" ;;
            codex) echo "$HOME/.codex/skills" ;;
            opencode) echo "${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills" ;;
            *) return 1 ;;
        esac
    else
        case "$h" in
            agents) echo "$PWD/.agents/skills" ;;
            deepagents) echo "$PWD/.deepagents/skills" ;;
            claude) echo "$PWD/.claude/skills" ;;
            codex) echo "$PWD/.codex/skills" ;;
            opencode) echo "$PWD/.opencode/skills" ;;
            *) return 1 ;;
        esac
    fi
}

HARNESSES=()
while [ $# -gt 0 ]; do
    case "$1" in
        --harness) HARNESSES+=("$2"); shift 2 ;;
        --scope) SCOPE="$2"; shift 2 ;;
        --target) TARGETS+=("$2"); shift 2 ;;
        --link) LINK=1; shift ;;
        --force) FORCE=1; shift ;;
        --init-config) DO_CONFIG=1; shift ;;
        --bin) DO_BIN=1; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
    esac
done
case "$SCOPE" in user|project) ;; *) echo "--scope must be user or project" >&2; exit 2 ;; esac

for h in "${HARNESSES[@]+"${HARNESSES[@]}"}"; do
    d="$(harness_dir "$h")" || { echo "unknown harness: $h" >&2; exit 2; }
    TARGETS+=("$d")
done

if [ ${#TARGETS[@]} -eq 0 ] && [ "$DO_CONFIG" = 0 ] && [ "$DO_BIN" = 0 ]; then
    usage; exit 2
fi

for t in "${TARGETS[@]+"${TARGETS[@]}"}"; do
    dest="$t/bitwarden"
    mkdir -p "$t"
    if [ -e "$dest" ] || [ -L "$dest" ]; then
        if [ "$FORCE" != 1 ]; then
            echo "skip: $dest exists (use --force to replace)"; continue
        fi
        # Never destroy private data someone may have dropped in the old skill dir.
        if [ -f "$dest/.env" ] && [ ! -L "$dest" ]; then
            echo "refusing to replace $dest: it contains a .env file. Move it to ~/.config/bw-agent/ first." >&2
            exit 1
        fi
        rm -rf -- "$dest"
    fi
    if [ "$LINK" = 1 ]; then
        ln -s "$SRC" "$dest"
    else
        cp -R "$SRC" "$dest"
    fi
    chmod +x "$dest/scripts/"*
    echo "installed: $dest"
done

if [ "$DO_BIN" = 1 ]; then
    mkdir -p "$BIN_DIR"
    for s in bw-agent bw-passkey-export; do
        ln -sfn "$SRC/scripts/$s" "$BIN_DIR/$s"
        echo "linked: $BIN_DIR/$s"
    done
    case ":$PATH:" in *":$BIN_DIR:"*) ;; *) echo "note: $BIN_DIR is not on PATH" ;; esac
fi

if [ "$DO_CONFIG" = 1 ]; then
    cfg_dir="${XDG_CONFIG_HOME:-$HOME/.config}/bw-agent"
    cfg="$cfg_dir/default.env"
    mkdir -p "$cfg_dir"; chmod 700 "$cfg_dir"
    if [ -e "$cfg" ]; then
        echo "config exists, left untouched: $cfg"
    else
        install -m 600 "$REPO/config/bw-agent.env.example" "$cfg"
        echo "created: $cfg (mode 600) — edit it, then run: bw-agent doctor"
    fi
fi
