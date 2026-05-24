"""Component 1 — Venture Brief loader and accessor.

The Venture Brief is structured input describing a venture's domain,
product, customer, voice, and constraints. The JSON Schema lives at
[`schemas/venture_brief.schema.json`](../../../schemas/venture_brief.schema.json)
and is the single source of truth shared between Ch.3 prose and the
framework code.

`VentureBrief` is a thin wrapper around the validated dict. We keep it
as a dict (not a fully-typed dataclass) so the schema remains the
authority — adding a field there is enough to make it readable
through `brief["new_field"]` without code changes here.

Convenience attribute access is provided for the top-level keys so
prose-friendly code (`brief.name`, `brief.voice.tone`) reads cleanly.

Citable in Ch.3 §"Venture Brief Schema".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

# Resolve the schema path relative to the framework repo root. The
# repo layout is fixed (schemas/ lives at the repo root, parallel to
# src/), so this works whether the package is installed editable or
# from a wheel that includes the schema as package data.
_DEFAULT_SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas" / "venture_brief.schema.json"
)


class _DotAccess:
    """Read-only dotted access wrapper over a nested mapping.

    Lets us write `brief.voice.tone` instead of `brief['voice']['tone']`
    without redefining every field as a dataclass attribute. Falling
    back through `__getattr__` keeps the schema authoritative.
    """

    __slots__ = ("_data",)

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def __getattr__(self, key: str) -> Any:
        if key in self._data:
            value = self._data[key]
            return _DotAccess(value) if isinstance(value, dict) else value
        raise AttributeError(key)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return self._data


class VentureBrief(_DotAccess):
    """Validated Venture Brief.

    Construct via `VentureBrief.from_file(path)` to validate against
    the schema, or `VentureBrief(data, validated=False)` to skip
    validation for tests.
    """

    def __init__(
        self,
        data: dict[str, Any],
        *,
        validated: bool = True,
        schema_path: Path | str | None = None,
    ) -> None:
        if validated:
            schema = json.loads(
                Path(schema_path or _DEFAULT_SCHEMA_PATH).read_text(encoding="utf-8")
            )
            jsonschema.validate(instance=data, schema=schema)
        super().__init__(data)

    @classmethod
    def from_file(cls, path: Path | str) -> "VentureBrief":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(data)

    @property
    def venture_id(self) -> str:
        return self._data["venture_id"]

    @property
    def name(self) -> str:
        return self._data["name"]
