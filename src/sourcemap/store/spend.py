"""The spend ledger: every paid call is charged to its run (docs/domain.md §12)."""

import sqlite3
from datetime import datetime


def charge(conn: sqlite3.Connection, run_id: int, service: str, usd: float, *, now: datetime,
           units: float = 1, ref: str = "") -> None:
    conn.execute("INSERT INTO spend (run_id, service, units, usd, ref, at) VALUES (?, ?, ?, ?, ?, ?)",
                 (run_id, service, units, usd, ref, now.isoformat(timespec="seconds")))
    conn.execute("UPDATE run SET spent_usd = spent_usd + ? WHERE id=?", (usd, run_id))


def remaining(conn: sqlite3.Connection, run_id: int) -> float:
    budget, spent = conn.execute("SELECT budget_usd, spent_usd FROM run WHERE id=?", (run_id,)).fetchone()
    return budget - spent
