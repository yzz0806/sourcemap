"""Freshness case table — the specification of measure.freshness (ADR 0012, docs/domain.md §9).

Title verdicts live 30 days; re-check window is the last 20% of life (the last 6 days).
Rows: name, days since the verdict was decided (on the as-of date), expected due?
"""

TITLE_RECHECK_CASES = [
    ("fresh title verdict (day 1) is not due", 1, False),
    ("day 23 is not yet in the last 20%", 23, False),
    ("day 24 enters the last 20% and is due", 24, True),
    ("day 29 is due", 29, True),
    ("expired verdict (day 31) is due", 31, True),
]

# expiry days by claim type (ADR 0012), checked against the specs
EXPIRY_DAYS = {
    ("org_chart", "title"): 30,
    ("org_chart", "reports_to"): 30,
    ("org_chart", "employment"): 60,
    ("academic_identity", "affiliation"): 60,
    ("academic_identity", "role"): 90,
    ("academic_identity", "exists"): 180,
}
