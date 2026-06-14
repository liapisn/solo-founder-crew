"""Persistent registry of in-flight Author Flow runs.

The LangGraph checkpointer preserves *graph state* across process
restarts. To make a run actually resume, the daemon also needs a small
amount of *operational* metadata that the graph state doesn't carry —
which role is drafting, what the original task was, which logical
channel to announce outcomes on, how many revisions the founder
allowed. That metadata lives here, in a JSON file next to the
checkpointer's SQLite database (``data/runs.json`` by default).

Schema (a single object keyed by ``thread_id``)::

    {
      "run-<n>": {
        "role":             "marketing",
        "task":             "Draft a launch teaser",
        "revisions":        3,
        "logical_channel":  "marketing",
        "status":           "running" | "shipped" | "killed" | "exhausted" | "error: ...",
        "latest_gate_channel_id": "1234567890",   # optional
        "latest_gate_message_id": "0987654321"    # optional
      },
      ...
    }

The ``latest_gate_*`` pair points at the most recently-posted HITL
gate message (Discord side). On respawn the daemon edits that message
to mark it stale ("🔄 Run resumed — see the latest gate above") and
strips its buttons, so the founder isn't confused by clickable-but-
dead controls. The fields are optional: pre-M1.6 registries on disk
do not have them and must still load.

Read on daemon startup, written on every state transition. Concurrent
writers are not expected (single daemon process); the registry uses
``Path.write_text`` with atomic-replace semantics on POSIX, which is
enough for our use.

This module deliberately has zero LangGraph or Discord imports so it
can be tested in isolation and stays cheap to import.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunRecord:
    """One row in the registry.

    ``status`` follows the ``AuthorFlowResult.status`` vocabulary,
    extended with ``"running"`` (no terminal state yet) and
    ``"error: <message>"`` (the driver raised before reaching
    terminal).

    ``latest_gate_channel_id`` / ``latest_gate_message_id`` track the
    most recently posted HITL gate message so the daemon can edit it
    on respawn (mark stale + strip buttons). Both default to ``None``
    for runs that died before the first gate posted, or for registries
    written before M1.6 added the fields.
    """

    thread_id: str
    role: str
    task: str
    revisions: int
    logical_channel: str
    status: str
    latest_gate_channel_id: str | None = None
    latest_gate_message_id: str | None = None

    @property
    def is_pending(self) -> bool:
        """True iff this run might still be resumed on startup —
        i.e. its driver task was alive when the process died.

        ``"running"`` is the only pending status; everything else
        (shipped / killed / exhausted / error: …) is terminal and
        ``crew.resume`` would be a no-op or fail on stale state.
        """
        return self.status == "running"

    def as_jsonable(self) -> dict[str, Any]:
        return asdict(self)


class RunsRegistry:
    """File-backed mapping from ``thread_id`` to ``RunRecord``.

    Designed for the single-process daemon use case. Each mutation
    immediately rewrites the file atomically (``tempfile`` + ``os.replace``
    on the same filesystem) so a crash mid-write cannot corrupt the
    registry.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._records: dict[str, RunRecord] = {}
        self._load()

    # ── public surface ────────────────────────────────────────────────────

    @property
    def path(self) -> Path:
        return self._path

    def get(self, thread_id: str) -> RunRecord | None:
        return self._records.get(thread_id)

    def all(self) -> tuple[RunRecord, ...]:
        return tuple(self._records.values())

    def pending(self) -> tuple[RunRecord, ...]:
        """Runs whose driver was alive when the process died."""
        return tuple(r for r in self._records.values() if r.is_pending)

    def put(self, record: RunRecord) -> None:
        """Insert or replace a record. Writes the file synchronously."""
        self._records[record.thread_id] = record
        self._flush()

    def set_status(self, thread_id: str, status: str) -> None:
        """Update only the status of an existing record. Writes the file."""
        existing = self._records.get(thread_id)
        if existing is None:
            return
        self._records[thread_id] = RunRecord(
            thread_id=existing.thread_id,
            role=existing.role,
            task=existing.task,
            revisions=existing.revisions,
            logical_channel=existing.logical_channel,
            status=status,
            latest_gate_channel_id=existing.latest_gate_channel_id,
            latest_gate_message_id=existing.latest_gate_message_id,
        )
        self._flush()

    def set_latest_gate(
        self, thread_id: str, *, channel_id: str, message_id: str
    ) -> None:
        """Record the Discord coordinates of the most recently posted
        HITL gate for this run.

        Called each time a gate message is posted (turn 1 and every
        revision). On respawn the daemon uses these coordinates to mark
        the stale message before letting the resumed flow post a fresh
        gate. No-op if the thread_id is not in the registry — the
        daemon's "/draft" handler always inserts before the first gate
        posts, so this guards against races, not against typical use.
        """
        existing = self._records.get(thread_id)
        if existing is None:
            return
        self._records[thread_id] = RunRecord(
            thread_id=existing.thread_id,
            role=existing.role,
            task=existing.task,
            revisions=existing.revisions,
            logical_channel=existing.logical_channel,
            status=existing.status,
            latest_gate_channel_id=channel_id,
            latest_gate_message_id=message_id,
        )
        self._flush()

    def remove(self, thread_id: str) -> None:
        """Drop a record (e.g. stale because the checkpoint no longer
        has matching state). Writes the file."""
        self._records.pop(thread_id, None)
        self._flush()

    # ── persistence ───────────────────────────────────────────────────────

    def _load(self) -> None:
        if not self._path.is_file():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            # Corrupt or unreadable file is treated as empty; the
            # daemon logs and continues. A future polish would rotate
            # the broken file aside (``runs.json.broken-<ts>``).
            return
        if not isinstance(raw, dict):
            return
        for tid, payload in raw.items():
            if not isinstance(payload, dict):
                continue
            try:
                latest_channel = payload.get("latest_gate_channel_id")
                latest_message = payload.get("latest_gate_message_id")
                self._records[tid] = RunRecord(
                    thread_id=tid,
                    role=str(payload["role"]),
                    task=str(payload["task"]),
                    revisions=int(payload.get("revisions", 0)),
                    logical_channel=str(payload.get("logical_channel", "")),
                    status=str(payload.get("status", "running")),
                    latest_gate_channel_id=(
                        str(latest_channel) if latest_channel is not None else None
                    ),
                    latest_gate_message_id=(
                        str(latest_message) if latest_message is not None else None
                    ),
                )
            except (KeyError, ValueError, TypeError):
                # Skip malformed entries; never propagate.
                continue

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Serialise as a thread_id-keyed object; drop the redundant
        # ``thread_id`` field inside each row since it's the key, and
        # omit gate fields whose values are still ``None`` so the file
        # stays narrow until those coordinates are known.
        payload = {
            tid: {
                k: v
                for k, v in asdict(rec).items()
                if k != "thread_id" and v is not None
            }
            for tid, rec in self._records.items()
        }
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        # Atomic replace: write to a sibling temp file then rename.
        tmp_fd, tmp_path = tempfile.mkstemp(
            prefix=".runs.", suffix=".json.tmp", dir=str(self._path.parent)
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(data)
            os.replace(tmp_path, self._path)
        except Exception:
            # Best-effort cleanup of the orphan tmp file.
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
