"""Schema migrations and the idempotent seed — store.db, store.seed (stage 2 checks 1–2)."""

import json
from pathlib import Path

from sourcemap.domain.specs import ALL_SPECS
from sourcemap.store.db import connect, migrate
from sourcemap.store.seed import load_seed_files, seed

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "units_small.json"


def fresh(tmp_path):
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    return conn


def small_seed_data():
    data = load_seed_files(ROOT / "seeds", units_file=FIXTURE)
    return data


def counts(conn):
    tables = ["data_type", "claim_type", "segment", "probe_unit", "panel_member", "source", "offer", "adapter"]
    return {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in tables}


def test_migrate_creates_tables_and_is_repeatable(tmp_path):
    conn = fresh(tmp_path)
    migrate(conn)  # second time: nothing to do
    names = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ["raw_fetch", "record", "claim", "verification", "score", "map_snapshot", "run", "job",
              "gate_decision", "run_event", "identifier_check", "known_answer_trial", "entity_event"]:
        assert t in names
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_verification_has_no_link_to_search_hits(tmp_path):
    """R2: search results are never evidence — the schema has no such foreign key."""
    conn = fresh(tmp_path)
    fks = conn.execute("SELECT \"table\" FROM pragma_foreign_key_list('verification')").fetchall()
    assert ("search_hit",) not in fks


def test_seed_twice_changes_nothing(tmp_path):
    conn = fresh(tmp_path)
    data = small_seed_data()
    seed(conn, ALL_SPECS, data)
    first = counts(conn)
    seed(conn, ALL_SPECS, data)
    assert counts(conn) == first
    assert first["data_type"] == 2
    assert first["probe_unit"] == 3


def test_segments_form_a_tree_under_all(tmp_path):
    conn = fresh(tmp_path)
    seed(conn, ALL_SPECS, small_seed_data())
    rows = conn.execute(
        "SELECT s.slug, p.slug FROM segment s LEFT JOIN segment p ON p.id = s.parent_id"
    ).fetchall()
    roots = [r for r in rows if r[1] is None]
    assert sorted(r[0] for r in roots) == ["all", "all"]
    assert all(parent == "all" for slug, parent in rows if slug != "all")


def test_unit_is_in_its_segment_with_identifiers(tmp_path):
    conn = fresh(tmp_path)
    seed(conn, ALL_SPECS, small_seed_data())
    seg, ids = conn.execute(
        "SELECT s.slug, u.identifiers_json FROM probe_unit u JOIN panel_member pm ON pm.probe_unit_id=u.id "
        "JOIN segment s ON s.id=pm.segment_id WHERE u.slug='samsung-electronics'"
    ).fetchone()
    assert seg == "kr_listed"
    assert json.loads(ids)["dart_corp_code"] == "00126380"


def test_sources_have_lineage_offers_and_adapters_with_keys(tmp_path):
    conn = fresh(tmp_path)
    seed(conn, ALL_SPECS, small_seed_data())
    lineage, by_claim = conn.execute(
        "SELECT lineage, lineage_by_claim_json FROM source WHERE slug='openalex'"
    ).fetchone()
    assert lineage == "openalex" and json.loads(by_claim) == {"profile_link": "orcid"}
    keys = conn.execute(
        "SELECT a.keys_json FROM adapter a JOIN source s ON s.id=a.source_id WHERE s.slug='dart'"
    ).fetchone()[0]
    assert json.loads(keys) == ["OPENDART_API_KEY"]
    offered = {r[0] for r in conn.execute(
        "SELECT g.slug FROM offer o JOIN source s ON s.id=o.source_id JOIN segment g ON g.id=o.segment_id "
        "WHERE s.slug='dart'")}
    assert offered == {"kr_listed"}


def test_real_seed_content_counts(tmp_path):
    """Stage 2 check 2 on the real seeds/: 2 data types, 16 companies, 17 departments."""
    conn = fresh(tmp_path)
    seed(conn, ALL_SPECS, load_seed_files(ROOT / "seeds"))
    per_type = dict(conn.execute(
        "SELECT d.slug, count(*) FROM probe_unit u JOIN data_type d ON d.id=u.data_type_id GROUP BY d.slug"
    ).fetchall())
    assert per_type == {"org_chart": 16, "academic_identity": 17}
