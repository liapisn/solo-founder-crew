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
        "status":           "running" | "shipped" | "killed" | "exhausted" | "error: ..."
      },
      ...
    }

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
    """

    thread_id: str
    role: str
    task: str
    revisions: int
    logical_channel: str
    status: str

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
                self._records[tid] = RunRecord(
                    thread_id=tid,
                    role=str(payload["role"]),
                    task=str(payload["task"]),
                    revisions=int(payload.get("revisions", 0)),
                    logical_channel=str(payload.get("logical_channel", "")),
                    status=str(payload.get("status", "running")),
                )
            except (KeyError, ValueError, TypeError):
                # Skip malformed entries; never propagate.
                continue

    def _flush(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        # Serialise as a thread_id-keyed object; drop the redundant
        # ``thread_id`` field inside each row since it's the key.
        payload = {
            tid: {k: v for k, v in asdict(rec).items() if k != "thread_id"}
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
