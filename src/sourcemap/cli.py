"""The `sourcemap` command line — the only entry point that reads `.env` (docs/components/pipeline.md#cli).

Stage 2 commands: `seed` (load starting content; `--check-ids` also checks every identifier),
`ids` (print the latest identifier checks), `counts` (what is in the database).
"""

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from sourcemap.domain.specs import ALL_SPECS
from sourcemap.pipeline.idcheck import run_checks
from sourcemap.sandbox.kit import Kit
from sourcemap.store.db import connect, migrate
from sourcemap.store.seed import load_seed_files, seed


def load_env(path: Path) -> dict[str, str]:
    """Read KEY=value lines from .env (no quotes, no export). Values are never printed."""
    env = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return {**env, **{k: v for k, v in os.environ.items() if k in env}}


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _db(args):
    conn = connect(Path(args.data_dir) / "sourcemap.sqlite")
    migrate(conn)
    return conn


def cmd_seed(args, env):
    conn = _db(args)
    seed(conn, ALL_SPECS, load_seed_files(args.seeds))
    cmd_counts(args, env, conn)
    if args.check_ids:
        print("\nChecking identifiers (polite fetches; LinkedIn is format-checked only)…")
        kit = Kit(min_interval_s=1.0, max_retries=2, timeout_s=20)
        rows = run_checks(conn, kit, now=_now(), dart_key=env.get("OPENDART_API_KEY") or None)
        _print_checks(rows)


def _print_checks(rows, summary=True):
    width = max((len(r[0]) for r in rows), default=10)
    for slug, kind, value, result, detail in rows:
        mark = "✓" if result in ("ok", "format_ok") else "✗"
        print(f"{mark} {slug:<{width}}  {kind:<21} {result:<18} {detail[:70]}")
    bad = [r for r in rows if r[3] not in ("ok", "format_ok")]
    if summary:
        print(f"\n{len(rows) - len(bad)} passed, {len(bad)} need a decision")
    else:
        print(f"\n{len(bad)} need a decision")


def cmd_ids(args, env):
    conn = _db(args)
    rows = conn.execute(
        """SELECT u.slug, c.kind, c.value, c.result, c.detail FROM identifier_check c
           JOIN probe_unit u ON u.id = c.probe_unit_id
           WHERE c.id = (SELECT max(id) FROM identifier_check x WHERE x.probe_unit_id=c.probe_unit_id AND x.kind=c.kind)
           ORDER BY u.data_type_id, u.id, c.kind""").fetchall()
    rows = [tuple(r) for r in rows if not args.failed or r["result"] not in ("ok", "format_ok")]
    _print_checks(rows, summary=not args.failed)


def cmd_counts(args, env, conn=None):
    conn = conn or _db(args)
    q = lambda sql: conn.execute(sql).fetchone()[0]  # noqa: E731
    print(f"data types: {q('SELECT count(*) FROM data_type')}")
    for slug, n in conn.execute("SELECT d.slug, count(u.id) FROM data_type d LEFT JOIN probe_unit u "
                                "ON u.data_type_id=d.id GROUP BY d.id ORDER BY d.id"):
        print(f"  {slug}: {n} probe units")
    for slug, segs in conn.execute(
            "SELECT d.slug, group_concat(s.slug || '←' || coalesce(p.slug, '·'), ', ') FROM segment s "
            "JOIN data_type d ON d.id=s.data_type_id LEFT JOIN segment p ON p.id=s.parent_id GROUP BY d.id"):
        print(f"  {slug} segments (child←parent): {segs}")
    print(f"sources: {q('SELECT count(*) FROM source')}, offers: {q('SELECT count(*) FROM offer')}, "
          f"adapters: {q('SELECT count(*) FROM adapter')}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="sourcemap")
    p.add_argument("--data-dir", default="data")
    p.add_argument("--env", default=".env")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seed", help="load starting content into the database (idempotent)")
    s.add_argument("--seeds", default="seeds")
    s.add_argument("--check-ids", action="store_true", help="also check every identifier (network)")
    i = sub.add_parser("ids", help="print the latest identifier checks")
    i.add_argument("--failed", action="store_true")
    sub.add_parser("counts", help="what is in the database")
    args = p.parse_args(argv)
    env = load_env(Path(args.env))
    {"seed": cmd_seed, "ids": cmd_ids, "counts": cmd_counts}[args.cmd](args, env)


if __name__ == "__main__":
    sys.exit(main())
