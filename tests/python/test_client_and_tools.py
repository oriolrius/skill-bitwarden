from __future__ import annotations

import base64
import json

import pytest

from skill_bitwarden import BitwardenClient, PolicyError, dispatch, openai_tools, redact_item, skill_dir
from skill_bitwarden.redact import REDACTED

from .conftest import ROOT, argv_log


def test_skill_dir_contains_skill_and_wrapper():
    d = skill_dir()
    assert (d / "SKILL.md").is_file()
    assert (d / "scripts" / "bw-agent").is_file()


def test_search_returns_no_secrets(fake_vault):
    results = BitwardenClient().search("example")
    assert {r["name"] for r in results} >= {"Example Service", "Another Example Login"}
    blob = json.dumps(results)
    assert "fixture-password" not in blob
    assert "fixture-totp-seed" not in blob
    svc = next(r for r in results if r["name"] == "Example Service")
    assert svc["has_password"] and svc["has_totp"] and svc["custom_fields"] == ["api-endpoint", "api-token"]


def test_get_item_is_redacted_by_default(fake_vault):
    item = BitwardenClient().get_item("11111111-1111-1111-1111-111111111111")
    assert item["login"]["password"] == REDACTED
    assert item["login"]["totp"] == REDACTED
    assert item["notes"] == REDACTED
    assert item["passwordHistory"][0]["password"] == REDACTED
    fields = {f["name"]: f["value"] for f in item["fields"]}
    assert fields["api-token"] == REDACTED
    assert fields["api-endpoint"] == "https://api.example.com"  # non-hidden kept
    assert item["login"]["username"] == "alice@example.com"


def test_get_item_reveal(fake_vault):
    item = BitwardenClient().get_item("Example Service", reveal=True)
    assert item["login"]["password"] == "fixture-password-not-real"


def test_get_field_standard_and_custom(fake_vault):
    c = BitwardenClient()
    assert c.get_field("Example Service") == "fixture-password-not-real"
    assert c.get_field("Example Service", "username") == "alice@example.com"
    assert c.get_field("Example Service", "totp") == "123456"
    assert c.get_field("Example Service", custom_field="api-token") == "fixture-hidden-field-value"
    with pytest.raises(ValueError):
        c.get_field("Example Service", "bogus")


def test_ambiguous_item_returns_error_json(fake_vault):
    out = json.loads(dispatch("bitwarden_get_secret", {"item": "example"}))
    assert out["error"] == "bitwarden error"
    assert "More than one result" in out["detail"]


def test_create_send_passes_secret_via_stdin(fake_vault):
    secret = "line1\nPassword: s3cret-value-xyz"
    res = BitwardenClient().create_text_send("demo", secret, max_access_count=2, expire_days=1)
    assert res["accessUrl"].startswith("https://vault.example.com/#/send/")
    assert res["maxAccessCount"] == 2
    assert "s3cret-value-xyz" not in argv_log(fake_vault)
    sent = json.loads(base64.b64decode((fake_vault / "last_send.b64").read_text()))
    assert sent["text"] == {"text": secret, "hidden": True}
    assert sent["deletionDate"].endswith("Z")


def test_create_login_with_generated_password(fake_vault):
    res = BitwardenClient().create_login("New", username="u@example.com", uris=["https://example.net"], generate=True)
    assert res["login"]["password"] == REDACTED
    created = json.loads(base64.b64decode((fake_vault / "last_create.b64").read_text()))
    assert created["login"]["password"] == "Gen3rated-Placeholder-Value"
    assert created["login"]["uris"] == [{"match": None, "uri": "https://example.net"}]
    assert "Gen3rated-Placeholder-Value" not in argv_log(fake_vault).replace("generate", "")


def test_update_item_dotted_keys(fake_vault):
    BitwardenClient().update_item("33333333-3333-3333-3333-333333333333", {"login.password": "n3w", "notes": "x"})
    edited = json.loads(base64.b64decode((fake_vault / "last_edit.b64").read_text()))
    assert edited["login"]["password"] == "n3w"
    assert edited["notes"] == "x"
    assert edited["login"]["username"] == "bob@example.org"


def test_read_only_blocks_writes_and_hides_write_tools(fake_vault, monkeypatch):
    monkeypatch.setenv("BW_AGENT_READ_ONLY", "1")
    names = {t["function"]["name"] for t in openai_tools()}
    assert "bitwarden_create_send" not in names and "bitwarden_search" in names
    with pytest.raises(PolicyError):
        BitwardenClient().create_login("x", password="y")
    out = json.loads(dispatch("bitwarden_create_send", {"name": "a", "text": "b"}))
    assert out["error"] == "blocked by policy"


def test_openai_tool_specs_are_valid():
    tools = openai_tools(read_only=False)
    assert len(tools) == 9
    for t in tools:
        fn = t["function"]
        assert t["type"] == "function"
        assert set(fn) == {"name", "description", "parameters"}
        assert fn["parameters"]["type"] == "object"
        assert fn["name"].startswith("bitwarden_")
    json.dumps(tools)


def test_dispatch_handles_bad_input(fake_vault):
    assert "unknown tool" in dispatch("nope", "{}")
    assert json.loads(dispatch("bitwarden_search", {"nope": 1}))["error"] == "invalid arguments"
    assert json.loads(dispatch("bitwarden_search", "not json"))["error"] == "invalid arguments"


def test_generate_password(fake_vault):
    out = json.loads(dispatch("bitwarden_generate_password", {"length": 30}))
    assert out["value"] == "Gen3rated-Placeholder-Value"


def test_redact_does_not_mutate_input():
    item = json.loads((ROOT / "tests" / "fixtures" / "items.json").read_text())[0]
    redact_item(item)
    assert item["login"]["password"] == "fixture-password-not-real"


def test_langchain_tools(fake_vault):
    pytest.importorskip("langchain_core")
    from skill_bitwarden.langchain import bitwarden_tools

    tools = {t.name: t for t in bitwarden_tools(read_only=False)}
    assert len(tools) == 9
    out = json.loads(tools["bitwarden_get_secret"].invoke({"item": "Example Service", "field": "username"}))
    assert out == {"value": "alice@example.com"}
    res = json.loads(tools["bitwarden_search"].invoke({"query": "note"}))
    assert res[0]["type"] == "secure_note"


def test_update_item_refuses_identity_keys(fake_vault):
    out = json.loads(
        dispatch("bitwarden_update_item", {"item_id": "33333333-3333-3333-3333-333333333333", "changes": {"id": "x"}})
    )
    assert out["error"] == "invalid arguments"
    assert not (fake_vault / "last_edit.b64").exists()


def test_dispatch_never_raises_on_timeout(fake_vault, monkeypatch):
    import subprocess

    def boom(*a, **k):
        raise subprocess.TimeoutExpired("bw-agent", 1)

    monkeypatch.setattr(subprocess, "run", boom)
    assert json.loads(dispatch("bitwarden_sync", {}))["error"] == "timeout"


def test_text_fields_with_secret_names_are_redacted():
    item = {"fields": [{"name": "API key", "value": "abc", "type": 0}, {"name": "region", "value": "eu", "type": 0}]}
    out = redact_item(item)
    assert out["fields"][0]["value"] == REDACTED
    assert out["fields"][1]["value"] == "eu"


def test_auth_failure_detail_reaches_the_model(fake_vault, monkeypatch):
    # issue #2: bw's own error must surface, not just "authentication failed"
    monkeypatch.setenv("FAKE_BW_UNLOCK_FAILS", "99")
    out = json.loads(dispatch("bitwarden_sync", {}))
    assert out["error"] == "bitwarden error"
    assert "KeyIdBackfillError" in out["detail"]
    assert "test-master-password" not in out["detail"]
