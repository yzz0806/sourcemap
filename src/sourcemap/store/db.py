"""SQLite connection and numbered migrations (ADR 0011, docs/data-model.md)."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"


def connect(path: str | Path) -> sqlite3.Connection:
    """Open the database in WAL mode with foreign keys on. Rows behave like tuples and dicts."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)  # autocommit; explicit BEGIN where needed
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Apply migrations/NNNN_*.sql not yet applied, in order. Returns the versions applied."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_migration (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    done = {r[0] for r in conn.execute("SELECT version FROM schema_migration")}
    applied = []
    for f in sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql")):
        version = f.stem
        if version in done:
            continue
        conn.execute("BEGIN")
        try:
            for statement in _statements(f.read_text()):
                conn.execute(statement)
            conn.execute("INSERT INTO schema_migration VALUES (?, ?)",
                         (version, datetime.now(UTC).isoformat(timespec="seconds")))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        applied.append(version)
    return applied


def _statements(sql: str) -> list[str]:
    """Split a migration file into statements (no semicolons inside our SQL strings)."""
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]
