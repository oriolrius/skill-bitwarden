"""Thin Python client over the `bw-agent` wrapper.

All authentication, configuration and policy enforcement lives in the shell
wrapper (single source of truth). This module only shells out to it with an
argv list (never through a shell) and passes payloads that may contain
secrets via stdin, so they never appear in process listings.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .paths import wrapper_path
from .redact import redact_item, summarize_item

#: Exit codes emitted by bw-agent for policy decisions.
POLICY_EXIT_CODES = {2: "blocked command", 3: "read-only mode", 4: "server mismatch"}

STANDARD_FIELDS = ("password", "username", "totp", "notes", "uri")

#: Top-level keys update_item refuses to change (identity / ownership).
PROTECTED_KEYS = frozenset({"id", "organizationId", "collectionIds", "object", "revisionDate", "creationDate"})


class BitwardenError(RuntimeError):
    """A bw-agent / bw invocation failed."""

    def __init__(self, returncode: int, message: str) -> None:
        self.returncode = returncode
        self.message = message
        super().__init__(f"bw-agent exited with {returncode}: {message}")


class PolicyError(BitwardenError):
    """The wrapper refused the operation (blocked command, read-only, ...)."""


def _clean_stderr(stderr: str) -> str:
    lines = [ln.strip() for ln in stderr.splitlines() if ln.strip()]
    return " | ".join(lines[-5:]) or "no error output"


def _env_flag(name: str, env: Mapping[str, str] | None = None) -> bool:
    value = (env if env is not None else os.environ).get(name, "")
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class BitwardenClient:
    """High-level, agent-oriented operations on a Bitwarden vault.

    Args:
        wrapper: Path to the ``bw-agent`` script. Defaults to ``$BW_AGENT_BIN``
            or the copy bundled with this package / repository.
        timeout: Seconds before a call is aborted (``$BW_AGENT_TIMEOUT``, 120).
        env: Extra environment variables for the wrapper (merged over
            ``os.environ``), e.g. ``{"BW_AGENT_PROFILE": "work"}``.
    """

    wrapper: Path | None = None
    timeout: float = field(default_factory=lambda: float(os.environ.get("BW_AGENT_TIMEOUT", "120")))
    env: Mapping[str, str] | None = None

    def __post_init__(self) -> None:
        self.wrapper = Path(self.wrapper) if self.wrapper else wrapper_path()

    # -- low level ---------------------------------------------------------

    def _environ(self) -> dict[str, str]:
        merged = dict(os.environ)
        if self.env:
            merged.update(self.env)
        return merged

    @property
    def read_only(self) -> bool:
        return _env_flag("BW_AGENT_READ_ONLY", self._environ())

    def run(self, *args: str, input_text: str | None = None) -> str:
        """Run ``bw-agent <args>`` and return stdout. Raises on failure."""
        proc = subprocess.run(  # noqa: S603 - argv list, no shell
            ["bash", str(self.wrapper), *args],
            input=input_text,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            env=self._environ(),
            check=False,
        )
        if proc.returncode != 0:
            exc = PolicyError if proc.returncode in POLICY_EXIT_CODES else BitwardenError
            raise exc(proc.returncode, _clean_stderr(proc.stderr))
        return proc.stdout

    def run_json(self, *args: str, input_text: str | None = None) -> Any:
        out = self.run(*args, input_text=input_text)
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            raise BitwardenError(0, f"expected JSON from bw {' '.join(args[:2])}") from exc

    @staticmethod
    def _encode(obj: Any) -> str:
        return base64.b64encode(json.dumps(obj).encode()).decode()

    # -- read --------------------------------------------------------------

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search items by name/URI/id. Returns metadata only — no secrets."""
        items = self.run_json("list", "items", "--search", query)
        return [summarize_item(i) for i in items[: max(1, limit)]]

    def get_item(self, item: str, reveal: bool = False) -> dict[str, Any]:
        """Full item JSON; secret values are redacted unless ``reveal``."""
        data = self.run_json("get", "item", item)
        return data if reveal else redact_item(data)

    def get_field(self, item: str, field: str = "password", custom_field: str | None = None) -> str:
        """Return one secret value: a standard field or a named custom field."""
        if custom_field:
            data = self.run_json("get", "item", item)
            for f in data.get("fields") or []:
                if f.get("name") == custom_field:
                    return "" if f.get("value") is None else str(f["value"])
            raise BitwardenError(1, f"custom field {custom_field!r} not found on item")
        if field not in STANDARD_FIELDS:
            raise ValueError(f"field must be one of {STANDARD_FIELDS} (or use custom_field)")
        return self.run("get", field, item).rstrip("\n")

    def list_sends(self) -> list[dict[str, Any]]:
        keys = ("id", "name", "accessUrl", "deletionDate", "accessCount", "maxAccessCount", "disabled")
        return [{k: s.get(k) for k in keys} for s in self.run_json("send", "list")]

    # -- utilities ---------------------------------------------------------

    def generate_password(
        self,
        length: int = 24,
        *,
        uppercase: bool = True,
        lowercase: bool = True,
        numbers: bool = True,
        special: bool = True,
        passphrase: bool = False,
        words: int = 5,
        separator: str = "-",
    ) -> str:
        if passphrase:
            args = ["generate", "--passphrase", "--words", str(words), "--separator", separator]
        else:
            flags = "".join(c for c, on in zip("ulns", (uppercase, lowercase, numbers, special), strict=True) if on)
            if not flags:
                raise ValueError("enable at least one character class")
            args = ["generate", f"-{flags}", "--length", str(max(5, length))]
        return self.run(*args).strip()

    def sync(self) -> str:
        return self.run("sync").strip()

    # -- write -------------------------------------------------------------

    def create_text_send(
        self,
        name: str,
        text: str,
        *,
        max_access_count: int = 3,
        expire_days: float = 3,
        hide_text: bool = True,
        password: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        """Create an expiring Bitwarden Send and return its share URL."""
        template = self.run_json("send", "template", "send.text")
        deletion = datetime.now(timezone.utc) + timedelta(days=expire_days)
        template.update(
            name=name,
            notes=notes,
            maxAccessCount=max_access_count,
            deletionDate=deletion.strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            password=password,
        )
        template["text"] = {"text": text, "hidden": hide_text}
        created = self.run_json("send", "create", input_text=self._encode(template))
        keys = ("id", "name", "accessUrl", "deletionDate", "maxAccessCount")
        return {k: created.get(k) for k in keys}

    def create_login(
        self,
        name: str,
        *,
        username: str | None = None,
        password: str | None = None,
        uris: Iterable[str] = (),
        notes: str | None = None,
        totp: str | None = None,
        folder_id: str | None = None,
        organization_id: str | None = None,
        collection_ids: Sequence[str] | None = None,
        generate: bool = False,
    ) -> dict[str, Any]:
        """Create a login item. ``generate=True`` creates a random password."""
        if generate and password is None:
            password = self.generate_password()
        item = {
            "organizationId": organization_id,
            "collectionIds": list(collection_ids) if collection_ids else None,
            "folderId": folder_id,
            "type": 1,
            "name": name,
            "notes": notes,
            "favorite": False,
            "fields": [],
            "login": {
                "uris": [{"match": None, "uri": u} for u in uris],
                "username": username,
                "password": password,
                "totp": totp,
            },
            "reprompt": 0,
        }
        created = self.run_json("create", "item", input_text=self._encode(item))
        return redact_item(created)

    def update_item(self, item_id: str, changes: Mapping[str, Any]) -> dict[str, Any]:
        """Shallow-merge ``changes`` (dotted keys allowed, e.g. ``login.password``)."""
        bad = sorted(k for k in changes if k.split(".", 1)[0] in PROTECTED_KEYS)
        if bad:
            raise ValueError(f"these keys cannot be changed with update_item: {bad}")
        data = self.run_json("get", "item", item_id)
        for key, value in changes.items():
            target = data
            *parents, leaf = key.split(".")
            for p in parents:
                if not isinstance(target.get(p), dict):
                    target[p] = {}
                target = target[p]
            target[leaf] = value
        updated = self.run_json("edit", "item", item_id, input_text=self._encode(data))
        return redact_item(updated)
