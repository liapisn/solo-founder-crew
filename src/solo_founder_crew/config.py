"""Runtime configuration for the live crew daemon (``app.py``).

12-factor by design: every operational knob comes from the environment or a
small ``crew.toml`` — never hard-coded — so moving the daemon from your local
machine to a VM later is a config change, not a code change (see
``docs/running-the-crew.md``).

Resolution order (lowest to highest precedence):
1. built-in defaults
2. ``crew.toml`` (path from ``SFC_CONFIG`` env, else ``./crew.toml``)
3. environment variables

This module is pure and side-effect-free (it reads a passed-in mapping, not
``os.environ`` directly), so it is unit-testable without a real environment.
"""
from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_BRIEF = "scenarios/fixtures/passly_brief.json"
DEFAULT_MODEL = "mock"  # "mock" (offline placeholder) | "real" (Anthropic)
DEFAULT_CHECKPOINTER = "sqlite:///./data/state.db"  # or "memory"


@dataclass(frozen=True)
class RuntimeConfig:
    """Resolved daemon configuration."""

    brief_path: Path
    model: str
    checkpointer_url: str
    guild_id: int | None
    discord_token: str | None
    channel_map: dict[str, str] = field(default_factory=dict)
    default_channel_id: str | None = None
    auto_create_channels: bool = True

    @property
    def use_real_llm(self) -> bool:
        return self.model == "real"

    def require_discord(self) -> None:
        """Raise a clear error if the secrets needed to connect are missing."""
        missing = []
        if not self.discord_token:
            missing.append("DISCORD_BOT_TOKEN")
        if self.guild_id is None:
            missing.append("SFC_GUILD_ID")
        if missing:
            raise SystemExit(
                "Cannot start the crew daemon — missing: "
                + ", ".join(missing)
                + ". See docs/running-the-crew.md."
            )


def _load_toml(config_path: Path | None) -> dict:
    if config_path is None or not config_path.is_file():
        return {}
    return tomllib.loads(config_path.read_text(encoding="utf-8"))


def load_runtime_config(
    env: Mapping[str, str],
    *,
    config_path: Path | str | None = None,
) -> RuntimeConfig:
    """Resolve a :class:`RuntimeConfig` from ``env`` + an optional TOML file.

    ``env`` is passed in (e.g. ``os.environ``) rather than read globally, so
    tests can drive it with a plain dict.
    """
    path = (
        Path(config_path)
        if config_path is not None
        else Path(env.get("SFC_CONFIG", "crew.toml"))
    )
    toml = _load_toml(path if path.is_file() else None)
    crew = toml.get("crew", {})
    channels = {str(k): str(v) for k, v in toml.get("channels", {}).items()}

    brief = env.get("SFC_BRIEF_PATH") or crew.get("brief") or DEFAULT_BRIEF
    model = env.get("SFC_MODEL") or crew.get("model") or DEFAULT_MODEL
    checkpointer = (
        env.get("SFC_CHECKPOINTER_URL")
        or crew.get("checkpointer")
        or DEFAULT_CHECKPOINTER
    )
    guild_raw = env.get("SFC_GUILD_ID") or (
        str(crew["guild_id"]) if "guild_id" in crew else None
    )
    default_channel = (
        env.get("SFC_DEFAULT_CHANNEL_ID") or crew.get("default_channel") or None
    )

    auto_raw = env.get("SFC_AUTO_CHANNELS")
    if auto_raw is not None:
        auto_create = auto_raw.strip().lower() not in ("0", "false", "no", "off")
    else:
        auto_create = bool(crew.get("auto_channels", True))

    return RuntimeConfig(
        brief_path=Path(brief),
        model=model,
        checkpointer_url=checkpointer,
        guild_id=int(guild_raw) if guild_raw else None,
        discord_token=env.get("DISCORD_BOT_TOKEN"),
        channel_map=channels,
        default_channel_id=str(default_channel) if default_channel else None,
        auto_create_channels=auto_create,
    )
