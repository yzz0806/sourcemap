"""The run event log — the live console of a run (docs/data-model.md)."""

import json
import sqlite3
from datetime import datetime


def log_event(conn: sqlite3.Connection, run_id: int, message: str, *, now: datetime, stage: str = "",
              level: str = "info", data: dict | None = None) -> int:
    return conn.execute(
        "INSERT INTO run_event (run_id, at, level, stage, message, data_json) VALUES (?, ?, ?, ?, ?, ?)",
        (run_id, now.isoformat(timespec="seconds"), level, stage, message, json.dumps(data or {})),
    ).lastrowid


def events_since(conn: sqlite3.Connection, run_id: int, after_id: int = 0) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM run_event WHERE run_id=? AND id>? ORDER BY id", (run_id, after_id)).fetchall()
