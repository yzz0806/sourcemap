"""Source health case table — the specification of measure.health (ADR 0012, docs/domain.md §9).

Each row: name, previous run stats (or None), this run stats, expected state. Stats are
(units_attempted, units_failed, shape_failures, units_valid, fingerprints-per-unit).
Priority: broken > shape_changed > degraded > changed > ok.
"""

from sourcemap.domain.vocab import HealthState

FP_A = {"airtable": frozenset({"f1", "f2", "f3", "f4", "f5"}), "gong": frozenset({"g1", "g2", "g3", "g4", "g5"})}
FP_A_ONE_CHANGED = {"airtable": frozenset({"f1", "f2", "f3", "f4", "fX"}), "gong": FP_A["gong"]}
FP_A_MANY_CHANGED = {"airtable": frozenset({"x1", "x2", "x3", "f4", "f5"}), "gong": frozenset({"y1", "y2", "g3", "g4", "g5"})}

HEALTH_CASES = [
    ("everything fine, first run", None, (4, 0, 0, 4, FP_A), HealthState.OK),
    ("nothing valid for any unit is broken", None, (4, 4, 0, 0, {}), HealthState.BROKEN),
    ("all fetched units fail to parse is still broken (broken wins)", None, (4, 0, 4, 0, {}), HealthState.BROKEN),
    ("half of fetched units fail to parse is shape changed", None, (4, 0, 2, 2, FP_A), HealthState.SHAPE_CHANGED),
    ("one unit's fetch failed is degraded", None, (4, 1, 0, 3, FP_A), HealthState.DEGRADED),
    ("first run can never be changed", None, (4, 0, 0, 4, FP_A_MANY_CHANGED), HealthState.OK),
    ("small change (1 of 11 fingerprints) is ok", (4, 0, 0, 4, FP_A), (4, 0, 0, 4, FP_A_ONE_CHANGED), HealthState.OK),
    ("many values differ (≥30%) is changed", (4, 0, 0, 4, FP_A), (4, 0, 0, 4, FP_A_MANY_CHANGED), HealthState.CHANGED),
    ("degraded beats changed", (4, 0, 0, 4, FP_A), (4, 1, 0, 3, FP_A_MANY_CHANGED), HealthState.DEGRADED),
    ("units only in one run are not compared", (4, 0, 0, 4, {"airtable": FP_A["airtable"]}),
     (4, 0, 0, 4, {"gong": FP_A["gong"]}), HealthState.OK),
]
