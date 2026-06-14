"""Tests for ``RunsRegistry`` — the daemon's per-run operational metadata.

The registry is the small piece of state outside the LangGraph
checkpointer that lets the daemon find pending runs after a restart.
These tests pin its file format, atomic-write behaviour, and
robustness to malformed input.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from solo_founder_crew.runs_registry import RunRecord, RunsRegistry


def _record(tid: str = "run-1", **overrides) -> RunRecord:
    base = dict(
        thread_id=tid,
        role="marketing",
        task="Draft a launch teaser",
        revisions=3,
        logical_channel="marketing",
        status="running",
    )
    base.update(overrides)
    return RunRecord(**base)


# ─── Round-trip ─────────────────────────────────────────────────────────────


def test_put_then_get_roundtrips(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "runs.json")
    rec = _record()
    reg.put(rec)

    again = RunsRegistry(tmp_path / "runs.json")  # fresh load from disk
    assert again.get("run-1") == rec


def test_put_writes_file_in_documented_schema(tmp_path: Path) -> None:
    path = tmp_path / "runs.json"
    reg = RunsRegistry(path)
    reg.put(_record(tid="run-x", task="Spec for wallet issuer"))
    raw = json.loads(path.read_text(encoding="utf-8"))

    # Single top-level object keyed by thread_id; each row carries
    # role/task/revisions/logical_channel/status (no redundant
    # thread_id inside the row).
    assert set(raw) == {"run-x"}
    row = raw["run-x"]
    assert "thread_id" not in row
    assert row == {
        "role": "marketing",
        "task": "Spec for wallet issuer",
        "revisions": 3,
        "logical_channel": "marketing",
        "status": "running",
    }


# ─── Pending filter ─────────────────────────────────────────────────────────


def test_pending_only_returns_running_records(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-1", status="running"))
    reg.put(_record(tid="run-2", status="shipped"))
    reg.put(_record(tid="run-3", status="killed"))
    reg.put(_record(tid="run-4", status="exhausted"))
    reg.put(_record(tid="run-5", status="error: ConnectionRefused"))
    reg.put(_record(tid="run-6", status="running"))

    pending_ids = {r.thread_id for r in reg.pending()}
    assert pending_ids == {"run-1", "run-6"}


# ─── set_status ─────────────────────────────────────────────────────────────


def test_set_status_updates_and_persists(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-7"))
    reg.set_status("run-7", "shipped")
    # Persisted: re-load from disk
    assert RunsRegistry(tmp_path / "runs.json").get("run-7").status == "shipped"


def test_set_status_on_unknown_id_is_noop(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.set_status("nonexistent", "shipped")  # must not raise
    assert reg.get("nonexistent") is None


# ─── remove ─────────────────────────────────────────────────────────────────


def test_remove_drops_record_and_persists(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-8"))
    reg.remove("run-8")
    assert reg.get("run-8") is None
    assert RunsRegistry(tmp_path / "runs.json").get("run-8") is None


# ─── Robustness on degenerate file states ──────────────────────────────────


def test_missing_file_is_empty_registry(tmp_path: Path) -> None:
    reg = RunsRegistry(tmp_path / "absent.json")
    assert reg.all() == ()


def test_malformed_json_is_treated_as_empty(tmp_path: Path) -> None:
    """A corrupt file must not crash daemon startup; the registry
    treats it as empty and the daemon continues. (A polish path
    would rotate the broken file aside.)"""
    path = tmp_path / "runs.json"
    path.write_text("not valid json {{{", encoding="utf-8")
    reg = RunsRegistry(path)
    assert reg.all() == ()


def test_row_with_unexpected_shape_is_skipped(tmp_path: Path) -> None:
    """A row missing required keys (or with the wrong type) must be
    skipped, not crash the load. Well-formed siblings survive."""
    path = tmp_path / "runs.json"
    path.write_text(
        json.dumps(
            {
                "ok": {
                    "role": "marketing",
                    "task": "x",
                    "revisions": 1,
                    "logical_channel": "marketing",
                    "status": "running",
                },
                "missing_role": {  # no "role" key
                    "task": "x",
                    "revisions": 1,
                    "logical_channel": "marketing",
                    "status": "running",
                },
                "wrong_type": "this should be a dict, not a string",
            }
        ),
        encoding="utf-8",
    )
    reg = RunsRegistry(path)
    ids = {r.thread_id for r in reg.all()}
    assert ids == {"ok"}


def test_atomic_write_does_not_leave_tmp_files(tmp_path: Path) -> None:
    """The atomic-replace write path must not leave stray ``.runs.*.tmp``
    files lying around on a normal write."""
    reg = RunsRegistry(tmp_path / "runs.json")
    for i in range(3):
        reg.put(_record(tid=f"run-{i}"))
    leftover = list(tmp_path.glob(".runs.*"))
    assert leftover == []


# ─── is_pending convenience ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    "status,expected",
    [
        ("running", True),
        ("shipped", False),
        ("killed", False),
        ("exhausted", False),
        ("error: anything", False),
    ],
)
def test_is_pending_property(status: str, expected: bool) -> None:
    assert _record(status=status).is_pending is expected


# ─── Latest gate coordinates (M1.6: stale-gate edit on respawn) ─────────────


def test_latest_gate_defaults_to_none(tmp_path: Path) -> None:
    """Fresh registries hold no gate coordinates until a gate posts."""
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-a"))
    rec = reg.get("run-a")
    assert rec is not None
    assert rec.latest_gate_channel_id is None
    assert rec.latest_gate_message_id is None


def test_set_latest_gate_persists_and_roundtrips(tmp_path: Path) -> None:
    path = tmp_path / "runs.json"
    reg = RunsRegistry(path)
    reg.put(_record(tid="run-b"))
    reg.set_latest_gate("run-b", channel_id="1234", message_id="9876")

    reloaded = RunsRegistry(path).get("run-b")
    assert reloaded is not None
    assert reloaded.latest_gate_channel_id == "1234"
    assert reloaded.latest_gate_message_id == "9876"


def test_set_latest_gate_unknown_id_is_noop(tmp_path: Path) -> None:
    """The daemon's /draft handler always inserts before the first gate
    posts; this is defensive against a race with a removed/cleared
    record."""
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.set_latest_gate("nope", channel_id="x", message_id="y")
    assert reg.get("nope") is None


def test_set_latest_gate_overwrites_on_revision(tmp_path: Path) -> None:
    """Each revision posts a new gate message — the registry should
    track the *latest* one so respawn edits the right message."""
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-c"))
    reg.set_latest_gate("run-c", channel_id="C", message_id="m1")  # turn 1
    reg.set_latest_gate("run-c", channel_id="C", message_id="m2")  # revision
    rec = reg.get("run-c")
    assert rec is not None
    assert rec.latest_gate_message_id == "m2"


def test_set_status_preserves_gate_coordinates(tmp_path: Path) -> None:
    """Status updates (running → shipped, etc.) must not clobber the
    gate coordinates. If they did, a record that completed quickly
    would lose the message_id before respawn could read it."""
    reg = RunsRegistry(tmp_path / "runs.json")
    reg.put(_record(tid="run-d"))
    reg.set_latest_gate("run-d", channel_id="C", message_id="M")
    reg.set_status("run-d", "shipped")
    rec = reg.get("run-d")
    assert rec is not None
    assert rec.latest_gate_message_id == "M"
    assert rec.status == "shipped"


def test_loader_accepts_pre_m16_files_without_gate_fields(tmp_path: Path) -> None:
    """Backward compat: a runs.json written before the gate-tracking
    fields existed must still load. Missing fields default to None."""
    path = tmp_path / "runs.json"
    path.write_text(
        json.dumps(
            {
                "legacy-run": {
                    "role": "marketing",
                    "task": "x",
                    "revisions": 1,
                    "logical_channel": "marketing",
                    "status": "running",
                    # NB: no latest_gate_* keys
                }
            }
        ),
        encoding="utf-8",
    )
    reg = RunsRegistry(path)
    rec = reg.get("legacy-run")
    assert rec is not None
    assert rec.role == "marketing"
    assert rec.latest_gate_channel_id is None
    assert rec.latest_gate_message_id is None


def test_flush_omits_none_gate_fields(tmp_path: Path) -> None:
    """The serialised JSON should not carry ``null`` for gate
    coordinates that were never set — keeps the file narrow until
    those values exist."""
    path = tmp_path / "runs.json"
    reg = RunsRegistry(path)
    reg.put(_record(tid="run-e"))  # no gate posted yet
    raw = json.loads(path.read_text(encoding="utf-8"))
    row = raw["run-e"]
    assert "latest_gate_channel_id" not in row
    assert "latest_gate_message_id" not in row
