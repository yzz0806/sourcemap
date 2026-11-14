"""Demo steps 5–6: match theorg's Samsung people to DART executives, check employment and title
claims against DART (reference, tier 1), and score with the stage 1 rules.

Implements docs/plan/demo-samsung-marketing.md with ADR 0002 (accuracy), 0003 (reference method),
0004 (matching: here every pair goes to the judge because names cross scripts). Evidence: the raw
DART report and theorg page are in the raw store; each verdict quotes the DART row it used.
"""

import json
from datetime import datetime
from pathlib import Path

from sourcemap.domain.model import Verification
from sourcemap.domain.vocab import Method, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for

JUDGE_PROMPT = """You match people across two lists about Samsung Electronics and judge titles.

List A (theorg.com, crowd-edited): people with an English name and role.
List B (DART, the official 2025 annual report, executives as of 2025-12-31): Korean name (Hangul),
rank (사장=President, 부사장=Executive VP, 상무=VP/Corporate VP, 회장=Chairman, 사외이사=independent
director, 사내이사=inside director) and responsibility (담당업무).

For EACH person in List A:
1. Find the List B row that is the same person, by romanization of the Korean name AND a
   compatible role. Korean names are romanized in many ways (조성혁 = Seong H. Cho = Sung-hyuk Cho).
   If several rows could match, or none does, answer null. Never guess: a wrong match is worse
   than no match.
2. If matched, judge whether List A's role is consistent with List B's rank and responsibility:
   "consistent" (same job, wording may differ), "inconsistent" (a different job or rank), or
   "unclear". Quote the List B row you used, exactly as given.

Answer one JSON object only:
{"matches": [{"a_id": <id>, "b_index": <int or null>, "b_quote": "<row or empty>",
  "title_verdict": "consistent|inconsistent|unclear|null", "reason": "<one short sentence>"}]}
"""


def judge_input(theorg: list[dict], dart: list[dict]) -> str:
    a = "\n".join(f"{p['id']}\t{p['name']}\t{p['role'] or ''}" for p in theorg)
    b = "\n".join(f"{i}\t{r['name']}\t{r['title']}\t{r['responsibility']}" for i, r in enumerate(dart))
    return f"List A (id, name, role):\n{a}\n\nList B (index, name, rank, responsibility):\n{b}"


def measure(theorg: list[dict], dart: dict, matches: list[dict], *, decided_at: datetime) -> dict:
    """Verdicts, scores and coverage. Pure given the judge's answers."""
    rows = dart["all"]
    marketing_idx = {i for i, r in enumerate(rows) if r in dart["marketing"]}
    by_a = {m["a_id"]: m for m in matches}
    emp, title, checks = [], [], []
    for p in theorg:
        m = by_a.get(p["id"]) or {}
        b = m.get("b_index")
        valid_b = isinstance(b, int) and 0 <= b < len(rows) and m.get("b_quote")
        if valid_b:
            e = Verdict.CORRECT
            tv = {"consistent": Verdict.CORRECT, "inconsistent": Verdict.WRONG}.get(m.get("title_verdict"),
                                                                                  Verdict.UNVERIFIABLE)
        else:
            # Not in DART: DART lists executives only, so a missing person may be a non-executive,
            # someone newer than the report, or a wrong claim. We can't tell: unverifiable.
            e = tv = Verdict.UNVERIFIABLE
        emp.append(Verification(p["id"], Method.REFERENCE, e, decided_at))
        title.append(Verification(p["id"], Method.REFERENCE, tv, decided_at))
        checks.append({"person": p, "dart_index": b if valid_b else None,
                       "dart_row": rows[b] if valid_b else None, "quote": m.get("b_quote", ""),
                       "employment": e.value, "title": tv.value, "reason": m.get("reason", ""),
                       "marketing": bool(valid_b and b in marketing_idx)})
    prior = prior_for(Tier.RESEARCHED)
    matched_marketing = {c["dart_index"] for c in checks if c["marketing"]}
    return {
        "checks": checks,
        "scores": {"employment": _est(estimate(emp, prior)), "title": _est(estimate(title, prior))},
        "coverage": {"dart_marketing_execs": len(marketing_idx), "on_theorg": len(matched_marketing),
                     "dart_execs": len(rows), "theorg_people": len(theorg),
                     "theorg_matched_to_dart": sum(1 for c in checks if c["dart_index"] is not None)},
    }


def _est(e) -> dict:
    return {"state": e.state.value, "mean": e.mean, "interval": [e.interval.lo, e.interval.hi] if e.interval else None,
            "n_decisive": e.n_decisive, "n_weighted": e.n_weighted, "n_correct": e.n_correct, "n_wrong": e.n_wrong,
            "n_unverifiable": e.n_unverifiable, "unverifiable_share": e.unverifiable_share,
            "prior": e.prior, "posterior": e.posterior}


def load(path: str | Path):
    return json.loads(Path(path).read_text())
