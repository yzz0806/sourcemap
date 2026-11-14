"""Raw store (write-once, content-addressed) and the database job queue (ADR 0011)."""

from datetime import datetime, timedelta

from sourcemap.domain.specs import ALL_SPECS
from sourcemap.store.db import connect, migrate
from sourcemap.store.queue import enqueue_run, fail_job, finish_job, heartbeat, lease_job
from sourcemap.store.rawstore import RawStore
from sourcemap.store.seed import seed

T0 = datetime(2026, 11, 14, 9, 0)


def test_same_content_twice_is_one_file(tmp_path):
    store = RawStore(tmp_path / "raw")
    h1 = store.put(b"<html>airtable</html>")
    h2 = store.put(b"<html>airtable</html>")
    assert h1 == h2
    files = [p for p in (tmp_path / "raw").rglob("*") if p.is_file()]
    assert len(files) == 1
    assert store.get(h1) == b"<html>airtable</html>"


def test_raw_store_never_rewrites_a_file(tmp_path):
    store = RawStore(tmp_path / "raw")
    h = store.put(b"x")
    before = store.path_of(h).stat().st_mtime_ns
    store.put(b"x")
    assert store.path_of(h).stat().st_mtime_ns == before


def _db(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    seed(conn, ALL_SPECS, {"segments": {}, "sources": {}, "units": {}})
    return conn


def test_lease_finish_and_order(tmp_path):
    conn = _db(tmp_path)
    run = enqueue_run(conn, "org_chart", "maintenance", "test", T0, 6.0, ["probe", "match"], now=T0)
    job = lease_job(conn, now=T0)
    assert job.stage == "probe" and job.run_id == run
    assert lease_job(conn, now=T0) is None  # the next stage waits for this one
    finish_job(conn, job.id, now=T0)
    assert lease_job(conn, now=T0).stage == "match"


def test_expired_lease_is_leased_again(tmp_path):
    conn = _db(tmp_path)
    enqueue_run(conn, "org_chart", "maintenance", "test", T0, 6.0, ["probe"], now=T0)
    job = lease_job(conn, now=T0, lease_s=60)
    assert lease_job(conn, now=T0 + timedelta(seconds=30)) is None
    again = lease_job(conn, now=T0 + timedelta(seconds=61))
    assert again is not None and again.id == job.id and again.attempts == 2


def test_heartbeat_extends_the_lease(tmp_path):
    conn = _db(tmp_path)
    enqueue_run(conn, "org_chart", "maintenance", "test", T0, 6.0, ["probe"], now=T0)
    job = lease_job(conn, now=T0, lease_s=60)
    heartbeat(conn, job.id, now=T0 + timedelta(seconds=50), lease_s=60)
    assert lease_job(conn, now=T0 + timedelta(seconds=70)) is None


def test_failed_job_marks_the_run_failed(tmp_path):
    conn = _db(tmp_path)
    run = enqueue_run(conn, "org_chart", "maintenance", "test", T0, 6.0, ["probe"], now=T0)
    job = lease_job(conn, now=T0)
    fail_job(conn, job.id, "boom", now=T0)
    assert conn.execute("SELECT status FROM run WHERE id=?", (run,)).fetchone()[0] == "failed"
