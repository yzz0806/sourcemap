"""The job queue in the database (ADR 0011).

A run is a chain of stages; each stage is one job. A job is leased with a deadline; a worker that
dies leaves an expired lease, and the job is leased again. Stages of one run go in order. Time is
always passed in (`now`), never read here.
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class Job:
    id: int
    run_id: int
    stage: str
    seq: int
    attempts: int


def _ts(t: datetime) -> str:
    return t.isoformat(timespec="seconds")


def enqueue_run(conn: sqlite3.Connection, data_type: str, kind: str, mode: str, as_of: datetime,
                budget_usd: float, stages: list[str], *, now: datetime, settings: dict | None = None,
                scenario: str | None = None) -> int:
    """Create a run and one queued job per stage. Returns the run id."""
    conn.execute("BEGIN")
    try:
        dt = conn.execute("SELECT id FROM data_type WHERE slug=?", (data_type,)).fetchone()[0]
        run_id = conn.execute(
            "INSERT INTO run (data_type_id, kind, mode, as_of, scenario, budget_usd, settings_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (dt, kind, mode, _ts(as_of), scenario, budget_usd, json.dumps(settings or {}), _ts(now)),
        ).lastrowid
        for i, stage in enumerate(stages, start=1):
            conn.execute("INSERT INTO job (run_id, stage, seq) VALUES (?, ?, ?)", (run_id, stage, i))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return run_id


def lease_job(conn: sqlite3.Connection, *, now: datetime, lease_s: int = 300) -> Job | None:
    """Lease the next runnable job: queued, or running with an expired lease, and every earlier
    stage of its run done. Returns None when nothing is runnable."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            """
            SELECT j.id, j.run_id, j.stage, j.seq, j.attempts FROM job j JOIN run r ON r.id = j.run_id
            WHERE r.status IN ('queued', 'running')
              AND (j.status = 'queued' OR (j.status = 'running' AND j.lease_until < ?))
              AND NOT EXISTS (SELECT 1 FROM job e WHERE e.run_id = j.run_id AND e.seq < j.seq AND e.status <> 'done')
            ORDER BY j.run_id, j.seq LIMIT 1
            """,
            (_ts(now),),
        ).fetchone()
        if row is None:
            conn.execute("COMMIT")
            return None
        conn.execute(
            "UPDATE job SET status='running', lease_until=?, attempts=attempts+1, "
            "started_at=COALESCE(started_at, ?) WHERE id=?",
            (_ts(now + timedelta(seconds=lease_s)), _ts(now), row["id"]),
        )
        conn.execute("UPDATE run SET status='running' WHERE id=? AND status='queued'", (row["run_id"],))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return Job(row["id"], row["run_id"], row["stage"], row["seq"], row["attempts"] + 1)


def heartbeat(conn: sqlite3.Connection, job_id: int, *, now: datetime, lease_s: int = 300) -> None:
    conn.execute("UPDATE job SET lease_until=? WHERE id=? AND status='running'",
                 (_ts(now + timedelta(seconds=lease_s)), job_id))


def finish_job(conn: sqlite3.Connection, job_id: int, *, now: datetime) -> None:
    """Mark a job done; when it was the run's last job, the run is done."""
    run_id = conn.execute("SELECT run_id FROM job WHERE id=?", (job_id,)).fetchone()[0]
    conn.execute("UPDATE job SET status='done', finished_at=?, lease_until=NULL WHERE id=?", (_ts(now), job_id))
    left = conn.execute("SELECT count(*) FROM job WHERE run_id=? AND status<>'done'", (run_id,)).fetchone()[0]
    if left == 0:
        conn.execute("UPDATE run SET status='done' WHERE id=? AND status='running'", (run_id,))


def fail_job(conn: sqlite3.Connection, job_id: int, error: str, *, now: datetime) -> None:
    run_id = conn.execute("SELECT run_id FROM job WHERE id=?", (job_id,)).fetchone()[0]
    conn.execute("UPDATE job SET status='failed', error=?, finished_at=? WHERE id=?", (error, _ts(now), job_id))
    conn.execute("UPDATE run SET status='failed' WHERE id=?", (run_id,))
