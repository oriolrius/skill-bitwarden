"""Keep secret values out of LLM context unless explicitly requested."""

from __future__ import annotations

import copy
import re
from typing import Any

REDACTED = "<redacted>"

ITEM_TYPES = {1: "login", 2: "secure_note", 3: "card", 4: "identity", 5: "ssh_key"}

# (section, key) pairs whose values are secret.
_SECRET_PATHS = (
    ("login", "password"),
    ("login", "totp"),
    ("card", "number"),
    ("card", "code"),
    ("identity", "ssn"),
    ("identity", "passportNumber"),
    ("identity", "licenseNumber"),
    ("sshKey", "privateKey"),
)

_HIDDEN_FIELD_TYPE = 1

# Text-type custom fields are often (mis)used for secrets; mask them too when
# the field name suggests so.
_SECRET_NAME_RE = re.compile(r"pass|secret|token|key|pin|otp|seed|credential|auth|private|cookie|session", re.I)


def _mask(value: Any) -> Any:
    return REDACTED if value not in (None, "") else value


def redact_item(item: dict[str, Any]) -> dict[str, Any]:
    """Return a deep copy of a vault item with every secret value masked.

    Non-secret metadata (name, username, URIs, ids, folder, custom field names
    and non-hidden custom field values) is preserved so the agent can reason
    about the item and then fetch exactly one secret with ``get_field``.
    """
    out = copy.deepcopy(item)
    for section, key in _SECRET_PATHS:
        sec = out.get(section)
        if isinstance(sec, dict) and key in sec:
            sec[key] = _mask(sec[key])
    if "notes" in out:
        out["notes"] = _mask(out["notes"])
    for f in out.get("fields") or []:
        secretish = f.get("type") == _HIDDEN_FIELD_TYPE or _SECRET_NAME_RE.search(f.get("name") or "")
        if secretish and "value" in f:
            f["value"] = _mask(f["value"])
    if out.get("passwordHistory"):
        out["passwordHistory"] = [
            {"lastUsedDate": h.get("lastUsedDate"), "password": REDACTED} for h in out["passwordHistory"]
        ]
    login = out.get("login")
    if isinstance(login, dict):
        for cred in login.get("fido2Credentials") or []:
            if "keyValue" in cred:
                cred["keyValue"] = REDACTED
    for att in out.get("attachments") or []:
        if "url" in att:
            att["url"] = REDACTED
    return out


def summarize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Compact, secret-free summary suitable for search results."""
    login = item.get("login") or {}
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "type": ITEM_TYPES.get(item.get("type"), item.get("type")),
        "username": login.get("username"),
        "uris": [u.get("uri") for u in login.get("uris") or [] if u.get("uri")],
        "folder_id": item.get("folderId"),
        "organization_id": item.get("organizationId"),
        "has_password": bool(login.get("password")),
        "has_totp": bool(login.get("totp")),
        "has_notes": bool(item.get("notes")),
        "has_passkey": bool(login.get("fido2Credentials")),
        "custom_fields": [f.get("name") for f in item.get("fields") or []],
    }
