"""Tests for the crew daemon's configuration resolution (config.py)."""
from __future__ import annotations

import pytest

from solo_founder_crew.config import (
    DEFAULT_BRIEF,
    DEFAULT_CHECKPOINTER,
    DEFAULT_MODEL,
    load_runtime_config,
)


def test_defaults_from_empty_env() -> None:
    cfg = load_runtime_config({}, config_path="/nonexistent.toml")
    assert str(cfg.brief_path) == DEFAULT_BRIEF
    assert cfg.model == DEFAULT_MODEL
    assert cfg.checkpointer_url == DEFAULT_CHECKPOINTER
    assert cfg.guild_id is None
    assert cfg.discord_token is None
    assert cfg.channel_map == {}
    assert cfg.use_real_llm is False


def test_env_overrides() -> None:
    env = {
        "SFC_BRIEF_PATH": "/tmp/b.json",
        "SFC_MODEL": "real",
        "SFC_CHECKPOINTER_URL": "memory",
        "SFC_GUILD_ID": "42",
        "DISCORD_BOT_TOKEN": "tok",
        "SFC_DEFAULT_CHANNEL_ID": "999",
    }
    cfg = load_runtime_config(env, config_path="/nonexistent.toml")
    assert str(cfg.brief_path) == "/tmp/b.json"
    assert cfg.use_real_llm is True
    assert cfg.checkpointer_url == "memory"
    assert cfg.guild_id == 42
    assert cfg.discord_token == "tok"
    assert cfg.default_channel_id == "999"


def test_toml_file_and_channel_map(tmp_path) -> None:
    toml = tmp_path / "crew.toml"
    toml.write_text(
        '[crew]\nbrief = "b.json"\nmodel = "mock"\n'
        '[channels]\nmarketing = "111"\nengineering = "222"\n',
        encoding="utf-8",
    )
    cfg = load_runtime_config({}, config_path=toml)
    assert str(cfg.brief_path) == "b.json"
    assert cfg.channel_map == {"marketing": "111", "engineering": "222"}


def test_env_beats_toml(tmp_path) -> None:
    toml = tmp_path / "crew.toml"
    toml.write_text('[crew]\nmodel = "mock"\n', encoding="utf-8")
    cfg = load_runtime_config({"SFC_MODEL": "real"}, config_path=toml)
    assert cfg.model == "real"


def test_require_discord_raises_when_missing() -> None:
    cfg = load_runtime_config({}, config_path="/nonexistent.toml")
    with pytest.raises(SystemExit, match="DISCORD_BOT_TOKEN"):
        cfg.require_discord()
