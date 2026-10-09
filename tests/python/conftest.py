from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAKE_BW_DIR = ROOT / "tests" / "fixtures" / "fake-bw"

_SCRUB = (
    "BW_SERVER",
    "BW_CLIENTID",
    "BW_CLIENTSECRET",
    "BW_PASSWORD",
    "BW_PASSWORD_FILE",
    "BW_PASSWORD_COMMAND",
    "BW_SESSION",
    "BW_AGENT_PROFILE",
    "BW_AGENT_CONFIG",
    "BW_AGENT_READ_ONLY",
    "BW_AGENT_ALLOW_EXPORT",
    "BW_AGENT_NO_CACHE",
    "BW_AGENT_CACHE_DIR",
    "BITWARDENCLI_APPDATA_DIR",
    "BW_HARD_RESET",
    "BW_AGENT_BIN",
)


@pytest.fixture
def fake_vault(tmp_path, monkeypatch):
    """Isolated HOME + fake bw CLI with valid credentials in the environment."""
    for k in _SCRUB:
        monkeypatch.delenv(k, raising=False)
    home = tmp_path / "home"
    home.mkdir()
    env = {
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(tmp_path / "config"),
        "XDG_CACHE_HOME": str(tmp_path / "cache"),
        "FAKE_BW_STATE": str(tmp_path / "state"),
        "BW_BIN_DIR": str(FAKE_BW_DIR),
        "BW_SERVER": "https://vault.example.com",
        "BW_CLIENTID": "test-client-id",
        "BW_CLIENTSECRET": "test-client-secret",
        "BW_PASSWORD": "test-master-password",
    }
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    return tmp_path / "state"


def argv_log(state: Path) -> str:
    p = state / "argv.log"
    return p.read_text() if p.exists() else ""


__all__ = ["argv_log", "os"]
