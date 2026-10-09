"""Harness-neutral tool definitions (OpenAI function-calling format).

The OpenAI ``tools`` schema is understood by DeepSeek's API and by most
OpenAI-compatible gateways/harnesses, so it is the canonical definition here.
Other adapters (LangChain/deepagents) are generated from it.

    from skill_bitwarden.tools import openai_tools, dispatch
    resp = client.chat.completions.create(model=..., messages=..., tools=openai_tools())
    for call in resp.choices[0].message.tool_calls or []:
        result = dispatch(call.function.name, call.function.arguments)
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Mapping
from typing import Any

from .client import STANDARD_FIELDS, BitwardenClient, BitwardenError, PolicyError

AGENT_INSTRUCTIONS = """\
You can access a Bitwarden password vault through the bitwarden_* tools.
Rules:
- Find items with bitwarden_search first; it returns metadata only (no secrets).
- Fetch exactly the one secret you need with bitwarden_get_secret. Never print
  secrets back to the user unless they explicitly asked to see them.
- NEVER send passwords, API keys or other secrets in plain text through any
  channel (email, chat, tickets, commit messages). Use bitwarden_create_send to
  create an expiring, access-limited link and share only that link. Defaults:
  expire in 3 days, max 3 accesses, text hidden. Report the recipient, the link
  and its constraints back to the user.
- Ask before creating, editing or deleting vault items.
"""

_WRITE = "write"

TOOL_SPECS: list[dict[str, Any]] = [
    {
        "name": "bitwarden_search",
        "description": "Search vault items by name, URL or id. Returns metadata only (id, name, username, URIs, flags), never secrets.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (item name, domain or id)."},
                "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_get_item",
        "description": "Get one item's full structure with all secret values redacted. Use the item id when several items match.",
        "parameters": {
            "type": "object",
            "properties": {"item": {"type": "string", "description": "Item id (preferred) or exact search term."}},
            "required": ["item"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_get_secret",
        "description": "Return ONE secret value from an item: password, username, totp (current one-time code), notes, uri, or a named custom field.",
        "parameters": {
            "type": "object",
            "properties": {
                "item": {"type": "string", "description": "Item id (preferred) or exact search term."},
                "field": {"type": "string", "enum": list(STANDARD_FIELDS), "default": "password"},
                "custom_field": {"type": "string", "description": "Name of a custom field; overrides 'field'."},
            },
            "required": ["item"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_generate_password",
        "description": "Generate a random password or passphrase (does not store it).",
        "parameters": {
            "type": "object",
            "properties": {
                "length": {"type": "integer", "minimum": 8, "maximum": 128, "default": 24},
                "special": {"type": "boolean", "default": True, "description": "Include special characters."},
                "passphrase": {"type": "boolean", "default": False},
                "words": {"type": "integer", "minimum": 3, "maximum": 20, "default": 5},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_list_sends",
        "description": "List existing Bitwarden Sends (share links) with their expiry and access counts.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "bitwarden_sync",
        "description": "Pull the latest vault data from the server.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "bitwarden_create_send",
        "description": "Create an expiring, access-limited Bitwarden Send for sharing secrets. Returns the share URL. Use this instead of ever sending secrets in plain text.",
        "x-kind": _WRITE,
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Descriptive label (not secret)."},
                "text": {"type": "string", "description": "The secret content to share; newlines are preserved."},
                "max_access_count": {"type": "integer", "minimum": 1, "maximum": 100, "default": 3},
                "expire_days": {"type": "number", "minimum": 0.01, "maximum": 31, "default": 3},
                "hide_text": {"type": "boolean", "default": True},
                "password": {"type": "string", "description": "Optional password required to open the Send."},
            },
            "required": ["name", "text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_create_login",
        "description": "Create a new login item. Set generate_password=true to store a freshly generated password.",
        "x-kind": _WRITE,
        "parameters": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "username": {"type": "string"},
                "password": {"type": "string"},
                "uris": {"type": "array", "items": {"type": "string"}},
                "notes": {"type": "string"},
                "generate_password": {"type": "boolean", "default": False},
            },
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "bitwarden_update_item",
        "description": 'Update fields of an existing item by id. \'changes\' maps dotted paths to new values, e.g. {"login.password": "...", "notes": "..."}.',
        "x-kind": _WRITE,
        "parameters": {
            "type": "object",
            "properties": {
                "item_id": {"type": "string", "description": "Exact item id (GUID)."},
                "changes": {"type": "object", "additionalProperties": True},
            },
            "required": ["item_id", "changes"],
            "additionalProperties": False,
        },
    },
]


def _handlers(c: BitwardenClient) -> dict[str, Callable[..., Any]]:
    return {
        "bitwarden_search": lambda query, limit=20: c.search(query, limit),
        "bitwarden_get_item": lambda item: c.get_item(item),
        "bitwarden_get_secret": lambda item, field="password", custom_field=None: {
            "value": c.get_field(item, field, custom_field)
        },
        "bitwarden_generate_password": lambda length=24, special=True, passphrase=False, words=5: {
            "value": c.generate_password(length, special=special, passphrase=passphrase, words=words)
        },
        "bitwarden_list_sends": lambda: c.list_sends(),
        "bitwarden_sync": lambda: {"result": c.sync()},
        "bitwarden_create_send": lambda name, text, max_access_count=3, expire_days=3, hide_text=True, password=None: (
            c.create_text_send(
                name,
                text,
                max_access_count=max_access_count,
                expire_days=expire_days,
                hide_text=hide_text,
                password=password,
            )
        ),
        "bitwarden_create_login": lambda name, username=None, password=None, uris=(), notes=None, generate_password=False: (
            c.create_login(
                name,
                username=username,
                password=password,
                uris=uris,
                notes=notes,
                generate=generate_password,
            )
        ),
        "bitwarden_update_item": lambda item_id, changes: c.update_item(item_id, changes),
    }


def tool_specs(read_only: bool | None = None, client: BitwardenClient | None = None) -> list[dict[str, Any]]:
    """Tool specs; write tools are omitted when read-only (``BW_AGENT_READ_ONLY``)."""
    if read_only is None:
        read_only = (client or BitwardenClient()).read_only
    return [s for s in TOOL_SPECS if not (read_only and s.get("x-kind") == _WRITE)]


def openai_tools(read_only: bool | None = None, client: BitwardenClient | None = None) -> list[dict[str, Any]]:
    """Specs wrapped as OpenAI/DeepSeek ``tools=[...]`` entries."""
    return [
        {"type": "function", "function": {k: v for k, v in s.items() if not k.startswith("x-")}}
        for s in tool_specs(read_only, client)
    ]


def dispatch(
    name: str,
    arguments: str | Mapping[str, Any] | None = None,
    client: BitwardenClient | None = None,
) -> str:
    """Execute a tool call and return a JSON string for the model.

    Errors are returned as ``{"error": ...}`` rather than raised, so the model
    can recover (e.g. disambiguate with an item id).
    """
    c = client or BitwardenClient()
    handler = _handlers(c).get(name)
    if handler is None:
        return json.dumps({"error": f"unknown tool {name!r}"})
    try:
        args = json.loads(arguments) if isinstance(arguments, str) and arguments.strip() else dict(arguments or {})
        result = handler(**args)
    except PolicyError as exc:
        return json.dumps({"error": "blocked by policy", "detail": exc.message})
    except BitwardenError as exc:
        return json.dumps({"error": "bitwarden error", "detail": exc.message})
    except (TypeError, ValueError) as exc:
        return json.dumps({"error": "invalid arguments", "detail": str(exc)})
    except subprocess.TimeoutExpired:
        return json.dumps({"error": "timeout", "detail": "bw-agent did not finish in time"})
    except Exception as exc:  # noqa: BLE001 - never crash the agent loop
        return json.dumps({"error": "internal error", "detail": type(exc).__name__})
    return json.dumps(result, ensure_ascii=False)
