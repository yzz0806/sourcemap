"""Load the hand-built starting content into the database; running it twice changes nothing.

Implements docs/domain.md §3 and docs/plan/stage-2-storage-and-seed.md. Seed content lives in
`seeds/sources.json` (segments, sources, offers, adapters) and `seeds/units.json` (panels and
identifiers). Data type specs come from `sourcemap.domain.specs` (ADR 0001).
"""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path

from sourcemap.domain.model import DataTypeSpec


def load_seed_files(seeds_dir: str | Path, units_file: str | Path | None = None) -> dict:
    """Read seeds/sources.json and seeds/units.json into one dict: segments, sources, units."""
    seeds_dir = Path(seeds_dir)
    sources = json.loads((seeds_dir / "sources.json").read_text())
    units_path = Path(units_file) if units_file else seeds_dir / "units.json"
    units = json.loads(units_path.read_text()) if units_path.exists() else {}
    return {
        "segments": sources.get("segments", {}),
        "sources": sources.get("sources", {}),
        "units": {k: v for k, v in units.items() if isinstance(v, list)},
    }


def seed(conn: sqlite3.Connection, specs: tuple[DataTypeSpec, ...], data: dict) -> None:
    """Upsert data types, claim types, segments, units, panels, sources, offers and adapters."""
    conn.execute("BEGIN")
    try:
        for spec in specs:
            dt = _upsert_data_type(conn, spec)
            seg_ids = _upsert_segments(conn, dt, data["segments"].get(spec.slug, []))
            for unit in data["units"].get(spec.slug, []):
                _upsert_unit(conn, dt, unit, seg_ids)
            for src in data["sources"].get(spec.slug, []):
                _upsert_source(conn, dt, src, seg_ids)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def _id(conn, sql, args) -> int:
    return conn.execute(sql, args).fetchone()[0]


def _upsert_data_type(conn, spec: DataTypeSpec) -> int:
    spec_json = json.dumps(asdict(spec), ensure_ascii=False, sort_keys=True)
    conn.execute(
        "INSERT INTO data_type (slug, name, spec_version, spec_json) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(slug) DO UPDATE SET name=excluded.name, spec_version=excluded.spec_version, "
        "spec_json=excluded.spec_json",
        (spec.slug, spec.name, spec.spec_version, spec_json),
    )
    dt = _id(conn, "SELECT id FROM data_type WHERE slug=?", (spec.slug,))
    for ct in spec.claim_types:
        conn.execute(
            "INSERT INTO claim_type (data_type_id, slug, value_kind, expiry_days, compare, field) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(data_type_id, slug) DO UPDATE SET "
            "value_kind=excluded.value_kind, expiry_days=excluded.expiry_days, compare=excluded.compare, "
            "field=excluded.field",
            (dt, ct.slug, ct.value_kind.value, ct.expiry_days, ct.compare.value, ct.field),
        )
    return dt


def _upsert_segments(conn, dt: int, segments: list[dict]) -> dict[str, int]:
    for s in segments:
        conn.execute(
            "INSERT INTO segment (data_type_id, slug, name, criteria) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(data_type_id, slug) DO UPDATE SET name=excluded.name, criteria=excluded.criteria",
            (dt, s["slug"], s["name"], s.get("criteria", "")),
        )
    ids = {r["slug"]: r["id"] for r in conn.execute("SELECT id, slug FROM segment WHERE data_type_id=?", (dt,))}
    for s in segments:
        parent = ids.get(s["parent"]) if s.get("parent") else None
        conn.execute("UPDATE segment SET parent_id=? WHERE id=?", (parent, ids[s["slug"]]))
    return ids


def _upsert_unit(conn, dt: int, unit: dict, seg_ids: dict[str, int]) -> None:
    identifiers = {k: v for k, v in unit.get("identifiers", {}).items() if v is not None}
    for meta in ("institution", "department", "aliases"):
        if unit.get(meta):
            identifiers[meta] = unit[meta]
    conn.execute(
        "INSERT INTO probe_unit (data_type_id, slug, name, identifiers_json) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(data_type_id, slug) DO UPDATE SET name=excluded.name, identifiers_json=excluded.identifiers_json",
        (dt, unit["slug"], unit["name"], json.dumps(identifiers, ensure_ascii=False, sort_keys=True)),
    )
    uid = _id(conn, "SELECT id FROM probe_unit WHERE data_type_id=? AND slug=?", (dt, unit["slug"]))
    seg = seg_ids[unit["segment"]]
    # A unit sits in exactly one leaf segment of its data type.
    conn.execute(
        "DELETE FROM panel_member WHERE probe_unit_id=? AND segment_id<>? AND segment_id IN "
        "(SELECT id FROM segment WHERE data_type_id=?)", (uid, seg, dt))
    conn.execute("INSERT OR IGNORE INTO panel_member (segment_id, probe_unit_id) VALUES (?, ?)", (seg, uid))


def _upsert_source(conn, dt: int, src: dict, seg_ids: dict[str, int]) -> None:
    conn.execute(
        "INSERT INTO source (data_type_id, slug, name, url, tier, subtype, lineage, lineage_by_claim_json, "
        "access, status, can_verify_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'approved', ?) "
        "ON CONFLICT(data_type_id, slug) DO UPDATE SET name=excluded.name, url=excluded.url, tier=excluded.tier, "
        "subtype=excluded.subtype, lineage=excluded.lineage, lineage_by_claim_json=excluded.lineage_by_claim_json, "
        "access=excluded.access, can_verify_json=excluded.can_verify_json",
        (dt, src["slug"], src["name"], src.get("url", ""), src["tier"], src["subtype"], src["lineage"],
         json.dumps(src.get("lineage_by_claim", {}), sort_keys=True), src.get("access", ""),
         json.dumps(src.get("can_verify", []))),
    )
    sid = _id(conn, "SELECT id FROM source WHERE data_type_id=? AND slug=?", (dt, src["slug"]))
    for seg in src.get("offers", []):
        conn.execute("INSERT OR IGNORE INTO offer (source_id, segment_id) VALUES (?, ?)", (sid, seg_ids[seg]))
    if a := src.get("adapter"):
        conn.execute(
            "INSERT INTO adapter (source_id, version, module, keys_json, supports_lookup) VALUES (?, 1, ?, ?, ?) "
            "ON CONFLICT(source_id, version) DO UPDATE SET module=excluded.module, keys_json=excluded.keys_json, "
            "supports_lookup=excluded.supports_lookup",
            (sid, a["module"], json.dumps(a.get("keys", [])), int(a.get("supports_lookup", False))),
        )
