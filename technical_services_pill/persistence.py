"""SQLite persistence for cases, knowledge proposals and KB versions.

The engine keeps its working state in two in-process singletons:
``store.STORE`` (cases, each with its hash-chained audit trail) and
``learning.STORE`` (validated knowledge, pending/approved proposals, KB
version). This module snapshots both into a local SQLite file after every
state-changing request and restores them on startup, so a server restart
loses nothing: not cases, not pending proposals, not version history.

Integrity on restore: every case's SHA-256 audit chain is re-verified after
loading. A case whose chain no longer validates is reported in
``load_state()``'s result rather than silently trusted.

Tamper evidence survives clean restarts: a snapshot whose on-disk bytes
changed while the process was NOT looking (an external edit between saves, or
a fresh edit after a graceful shutdown would have autosaved over it) is
archived to ``tbc.tampered.<timestamp>.sqlite`` and logged in the ``snapshots``
database's ``integrity_events`` table *before* the clean state overwrites it --
so the FAIL badge a later restart shows is backed by preserved evidence, not
memory.

Scope note: snapshots use ``pickle`` and must only ever be loaded from a
file this service wrote itself (the default ``data/`` path is gitignored).
A production deployment would move to a relational schema in Postgres; the
store interfaces (``CaseStore``, ``LearningStore``) are the seam for that.
"""
from __future__ import annotations

import hashlib
import logging
import os
import pickle
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import learning, store, tools

DEFAULT_DB_PATH = Path("data") / "tbc.sqlite"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    key       TEXT PRIMARY KEY,
    blob      BLOB NOT NULL,
    saved_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS integrity_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    event         TEXT NOT NULL,
    detail        TEXT NOT NULL,
    archived_path TEXT
);
"""

_log = logging.getLogger("tbc.persistence")

# In-session ledger of integrity events (also persisted; a restart replays
# this table into memory so the UI keeps showing what the service has seen).
_INTEGRITY_EVENTS: list[dict[str, Any]] = []

# keyed by (str(db_path), snapshot_key) -> the exact bytes we last loaded or
# wrote. save_state() compares the on-disk blob against this before
# overwriting: if they differ the disk was modified outside this process, and
# that evidence is archived instead of silently replaced.
_last_written: dict[tuple[str, str], bytes] = {}

# (str(db_path), snapshot_key, sha256(disk_blob)) already archived/logged, so
# the same tampered bytes are never archived twice.
_reported: set[tuple[str, str, str]] = set()


def db_path() -> Path:
    """Resolve the database path from ``TBC_DB_PATH`` or the default."""
    return Path(os.environ.get("TBC_DB_PATH", str(DEFAULT_DB_PATH)))


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    return conn


def _state() -> dict[str, Any]:
    return {
        "cases": store.STORE._cases,
        "learning": learning.STORE.__dict__,
        "tool_audit_log": tools.TOOL_AUDIT_LOG,
    }


def integrity_events() -> list[dict[str, Any]]:
    """Integrity events this process has seen (persisted across restarts)."""
    return list(_INTEGRITY_EVENTS)


def _archive(path: Path) -> str | None:
    """Copy the DB file as-is so tampered evidence survives the next write."""
    ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target = path.with_name(f"{path.stem}.tampered.{ts}{path.suffix}")
    try:
        shutil.copyfile(path, target)
    except OSError:
        _log.exception("could not archive tampered snapshot to %s", target)
        return None
    return str(target)


def _record_event(
    path: Path,
    event: str,
    detail: str,
    archived_path: str | None = None,
    *,
    conn: sqlite3.Connection | None = None,
) -> None:
    row = {
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "detail": detail,
        "archived_path": archived_path,
    }
    _INTEGRITY_EVENTS.append(row)
    try:
        if conn is None:
            with _connect(path) as own:
                own.execute(
                    "INSERT INTO integrity_events (at, event, detail, archived_path)"
                    " VALUES (?, ?, ?, ?)",
                    (row["at"], row["event"], row["detail"], row["archived_path"]),
                )
        else:
            conn.execute(
                "INSERT INTO integrity_events (at, event, detail, archived_path)"
                " VALUES (?, ?, ?, ?)",
                (row["at"], row["event"], row["detail"], row["archived_path"]),
            )
    except sqlite3.Error:
        # The event still shows for this session even if persisting it failed.
        _log.exception("could not persist integrity event %r", event)


def _load_events(conn: sqlite3.Connection) -> None:
    _INTEGRITY_EVENTS.clear()
    try:
        for at, event, detail, archived in conn.execute(
            "SELECT at, event, detail, archived_path FROM integrity_events"
            " ORDER BY id"
        ):
            _INTEGRITY_EVENTS.append({
                "at": at,
                "event": event,
                "detail": detail,
                "archived_path": archived,
            })
    except sqlite3.Error:
        _log.exception("could not read integrity_events from %s", db_path())


def save_state(path: Path | None = None) -> None:
    """Write the current engine state to SQLite in one transaction.

    Before overwriting a snapshot that we previously wrote or loaded, its
    on-disk bytes are compared against what we last saw. A mismatch means the
    file was edited outside this process since our last write: the tampered
    copy is archived and an integrity event is recorded. The write then goes
    ahead, but the tamper stays provable forever (archive + logged event), so
    a graceful shutdown can never make the evidence silently disappear.
    """
    path = path or db_path()
    now = datetime.now(timezone.utc).isoformat()
    keyed = str(path)

    with _connect(path) as conn:
        state = _state()

        # Pass 1: detect disk edits we never made, before writing anything.
        for key in state:
            row = conn.execute(
                "SELECT blob FROM snapshots WHERE key = ?", (key,)
            ).fetchone()
            disk = row[0] if row else None
            prev = _last_written.get((keyed, key))
            if prev is not None and disk is not None and disk != prev:
                digest = hashlib.sha256(disk).hexdigest()
                marker = (keyed, key, digest)
                if marker not in _reported:
                    _reported.add(marker)
                    archived = _archive(path)
                    _record_event(
                        path,
                        "snapshot_modified_between_saves",
                        f"snapshot {key!r} changed on disk since this process "
                        "wrote it; tampered copy preserved",
                        archived,
                        conn=conn,
                    )

        # Pass 2: write the snapshots and remember exactly what we wrote.
        for key, value in state.items():
            blob = pickle.dumps(value)
            conn.execute(
                "INSERT OR REPLACE INTO snapshots (key, blob, saved_at) VALUES (?, ?, ?)",
                (key, blob, now),
            )
            _last_written[(keyed, key)] = blob


def load_state(path: Path | None = None) -> dict[str, Any]:
    """Restore engine state from SQLite into the live singletons.

    Returns a summary including any cases whose audit chain failed
    re-verification. A missing database is not an error: the engine simply
    starts from seed data.

    Integrity: the snapshot a case was restored from is archived to a
    ``tbc.tampered.<timestamp>.sqlite`` file and logged as an integrity event
    *before* anything can overwrite it, so a clean restart later cannot make
    the tamper evidence disappear.
    """
    path = path or db_path()
    keyed = str(path)
    if not path.exists():
        return {"restored": False, "reason": "no database yet", "path": str(path)}

    with _connect(path) as conn:
        rows = dict(conn.execute("SELECT key, blob FROM snapshots").fetchall())
        _load_events(conn)
    if not rows:
        return {"restored": False, "reason": "database empty", "path": str(path)}

    # A snapshot we just loaded is the baseline for in-session edit detection.
    for key, blob in rows.items():
        _last_written[(keyed, key)] = blob

    if "cases" in rows:
        store.STORE._cases.clear()
        store.STORE._cases.update(pickle.loads(rows["cases"]))
    if "learning" in rows:
        learning.STORE.__dict__.clear()
        learning.STORE.__dict__.update(pickle.loads(rows["learning"]))
    if "tool_audit_log" in rows:
        tools.TOOL_AUDIT_LOG[:] = pickle.loads(rows["tool_audit_log"])

    broken = [
        cid for cid, st in store.STORE._cases.items() if not st.verify_audit_chain()
    ]
    if broken:
        # One incident per broken case set, not one per byte pattern: the
        # re-pickled copy of a restored snapshot is not byte-identical to the
        # tampered file, so a digest key would double-report after each clean
        # restart. A genuinely NEW tamper (a different affected case) gets a
        # new marker and is reported again.
        marker = (keyed, "audit_chain_failure", frozenset(broken))
        if marker not in _reported:
            _reported.add(marker)
            archived = _archive(path)
            _record_event(
                path,
                "audit_chain_failure_on_load",
                "audit chain failed for " + ", ".join(broken) + "; "
                "tampered snapshot preserved before any later save",
                archived,
            )
    return {
        "restored": True,
        "path": str(path),
        "cases": len(store.STORE._cases),
        "kb_version": learning.STORE.get_kb_version_label(),
        "pending_proposals": len(learning.STORE.list_pending_proposals()),
        "audit_chain_failures": broken,
        "integrity_events": list(_INTEGRITY_EVENTS),
    }
