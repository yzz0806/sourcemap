"""Leadership-change signals: match what sources reported to the SEC 8-K Item 5.02 reference and score
each source on accuracy, coverage, freshness and cost (US mega-cap only, for now).

Reference: data/sig/refs.json (scripts/sig_refs.py). Sources: data/sig/reads.json + search.json
(scripts/sig_sources.py). Rules as elsewhere: a reported change that matches a filed change is correct;
one that contradicts a filed change for the same person is wrong; anything the filings don't cover is
unverifiable, never wrong (absent ≠ false). Accuracy uses the stage 1 Beta estimate (ADR 0002).
Freshness = source publication date − 8-K filing date, in days (negative = the source was earlier).
"""

import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from sourcemap.domain.model import Verification
from sourcemap.domain.vocab import Method, Verdict
from sourcemap.measure.accuracy import estimate, prior_for
from sourcemap.measure.match import name_relation
from sourcemap.measure.names import normalise_name
from sourcemap.pipeline import demo_multi as M

T0 = date(2026, 11, 14)
COMPAT = {"appointed": {"appointed", "role_change"}, "role_change": {"appointed", "role_change"}, "departed": {"departed"}}


def _d(s):
    try:
        return date.fromisoformat((s or "")[:10])
    except ValueError:
        return None


def same_person(a: str, b: str) -> bool:
    na, nb = normalise_name(a), normalise_name(b)
    rel = name_relation(na, nb)
    if rel == "same":
        return True
    # borderline (initials, middle names): accept when the surnames agree and one name's tokens contain the other's
    return rel == "borderline" and bool(na.full & nb.full)


ROLE_KEYS = {
    "ceo": ("chief executive", "ceo"), "cfo": ("chief financial", "cfo"), "coo": ("chief operating", "coo"),
    "cto": ("chief technology", "cto"), "cao": ("accounting officer", "cao", "controller"), "cmo": ("chief marketing", "cmo"),
    "counsel": ("general counsel", "legal officer", "secretary"), "chair": ("chair",), "director": ("director", "board"),
    "president": ("president",), "evp": ("executive vice president", "evp"), "svp": ("senior vice president", "svp"),
    "people": ("people officer", "human resources", "hr"), "ops": ("operations",), "hardware": ("hardware",), "software": ("software",),
}
WINDOW = (-30, 365)  # a report counts for a filed change only if dated between 30 days before and a year after the filing


def role_keys(role: str | None) -> set[str]:
    r = (role or "").lower()
    return {k for k, words in ROLE_KEYS.items() if any(w in r for w in words)}


def match_event(ev: dict, refs: list[dict], published: date | None = None) -> tuple[str, dict | None]:
    """Verdict for one reported event against the company's reference events.

    Same person is not enough — people change roles several times. A filed change is a candidate only
    when the report's date (its stated effective date, else the page's publication date) falls in WINDOW around the
    filing, and the roles don't clearly differ. Same person + candidate + compatible change → correct;
    same person + candidate + opposite change → wrong; anything else → unverifiable.
    """
    # The report's own stated effective date says which event it is about; a page's publication date can be a
    # recent update of an old bio ("appointed CAO in 2016"), so it is only the fallback.
    anchor = _d(ev.get("effective_date")) or published
    rk = role_keys(ev.get("role"))
    cands = []
    for r in refs:
        rr = role_keys(r.get("role"))
        if not same_person(ev["person"], r["person"]):
            # Legal vs used first names (8-K "Jen-Hsun Huang", press "Jensen Huang"): same surname and the same
            # specific role (CEO, CFO, chair…) at the same company in the same window is the same person.
            sur_a, sur_b = normalise_name(ev["person"]).tokens, normalise_name(r["person"]).tokens
            surname_same = ev["person"].split()[-1].lower() == r["person"].split()[-1].lower()
            specific = (rk & rr) - {"director", "evp", "svp", "president", "ops"}
            if not (surname_same and specific and sur_a and sur_b):
                continue
        fd = _d(r["filing_date"])
        if anchor and fd and not (WINDOW[0] <= (anchor - fd).days <= WINDOW[1]):
            continue  # an older or later change of the same person — a different event
        if rk and rr and not (rk & rr):
            continue  # clearly a different role (e.g. CFO vs interim CEO) — a different event
        cands.append(r)
    if not cands:
        return "unverifiable", None
    ok = [r for r in cands if r["change"] in COMPAT.get(ev["change"], {ev["change"]})]
    if ok:
        return "correct", min(ok, key=lambda r: abs(((anchor or _d(r["filing_date"])) - _d(r["filing_date"])).days))
    # A contradiction is only "wrong" when we know the report is about the same moment: if it states an
    # effective date we can't read (e.g. "June 17", no year), it may describe another year — unverifiable.
    if ev.get("effective_date") and not _d(ev.get("effective_date")):
        return "unverifiable", None
    return "wrong", cands[0]


def build(root: Path) -> dict:
    refs = json.loads((root / "data/sig/refs.json").read_text())
    reads = json.loads((root / "data/sig/reads.json").read_text())
    search = json.loads((root / "data/sig/search.json").read_text())
    scost = M.search_cost_by_source(search)

    # Leadership changes only (compensation-only 5.02 items excluded), de-duplicated: the same change can be
    # filed twice (e.g. an amended 8-K) or listed twice in one filing — one per (person, change, month).
    ref_events = {}
    for slug, c in refs["companies"].items():
        seen, keep = set(), []
        for e in sorted(c["events"], key=lambda e: e["filing_date"]):
            if e.get("kind") == "compensation_only":
                continue
            key = (normalise_name(e["person"]).key, e["change"], e["filing_date"][:7])
            if key not in seen:
                seen.add(key)
                keep.append(e)
        ref_events[slug] = keep
    total_ref = sum(len(v) for v in ref_events.values())

    per_src = defaultdict(lambda: {"events": [], "pages": 0, "blocked": 0, "usd": 0.0, "companies": set(), "found": set(), "late": []})
    reported_by = defaultdict(list)  # ref event id -> [{source, url, published, days_late}]
    for page in reads:
        src, slug = page["source"], page["company"]
        s = per_src[src]
        s["companies"].add(slug)
        s["usd"] += page.get("extract_usd", 0)
        if page.get("status") != "ok":
            s["blocked"] += 1
            continue
        s["pages"] += 1
        pub = _d(page.get("published"))
        for ev in page.get("events", []):
            verdict, ref = match_event(ev, ref_events.get(slug, []), pub)
            late = (pub - _d(ref["filing_date"])).days if verdict == "correct" and pub and _d(ref["filing_date"]) else None
            s["events"].append({**ev, "company": slug, "url": page["url"], "published": page.get("published"),
                                "verdict": verdict, "ref_id": ref["id"] if ref else None, "ref_quote": ref["quote"] if ref else "",
                                "days_late": late})
            if verdict == "correct":
                s["found"].add(ref["id"])
                if late is not None:
                    s["late"].append(late)
                reported_by[ref["id"]].append({"source": src, "url": page["url"], "published": page.get("published"), "days_late": late})
    for (src, slug), usd in scost.items():
        if src in per_src:
            per_src[src]["usd"] += usd

    sources = []
    for src, s in per_src.items():
        tier = M.tier_of(src, {"own_domains": ["nvidia.com", "apple.com", "microsoft.com"]})  # newsrooms are first party
        # one verdict per (source, reference event or reported claim): dedupe repeated reports of the same change
        seen, vs = set(), []
        for i, ev in enumerate(s["events"]):
            key = (ev["ref_id"] or f"{ev['company']}|{ev['person']}|{ev['change']}", ev["verdict"])
            if key in seen:
                continue
            seen.add(key)
            vs.append(Verification(i, Method.REFERENCE, Verdict(ev["verdict"]), T0))
        e = estimate(vs, prior_for(tier))
        sources.append({
            "source": src, "tier": int(tier), "pages": s["pages"], "blocked": s["blocked"], "companies": sorted(s["companies"]),
            "accuracy": {"state": e.state.value, "mean": e.mean, "interval": [e.interval.lo, e.interval.hi] if e.interval else None,
                         "n": e.n_decisive, "n_wrong": e.n_wrong, "unverifiable_share": e.unverifiable_share},
            "coverage": {"found": len(s["found"]), "total": total_ref},
            "freshness": {"median_days": statistics.median(s["late"]) if s["late"] else None, "n": len(s["late"]),
                          "values": sorted(s["late"])},
            "usd": s["usd"], "events": s["events"],
        })
    sources.sort(key=lambda x: (-x["coverage"]["found"], -(x["accuracy"]["mean"] or 0)))
    timeline = []
    for slug, evs in ref_events.items():
        for r in evs:
            timeline.append({**r, "company": slug, "reported_by": sorted(reported_by.get(r["id"], []),
                             key=lambda x: (x["days_late"] is None, x["days_late"] if x["days_late"] is not None else 0))})
    timeline.sort(key=lambda r: r["filing_date"], reverse=True)
    return {"segment": "us_listed", "window": refs.get("window"), "total_ref_events": total_ref,
            "filings": {slug: len(c.get("filings", [])) for slug, c in refs["companies"].items()},
            "sources": sources, "timeline": timeline,
            "spent_usd": search.get("spent_usd", 0) + sum(p.get("extract_usd", 0) for p in reads)}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    out = build(root)
    (root / "data/sig/measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1, default=list))
    for s in out["sources"][:12]:
        a, f = s["accuracy"], s["freshness"]
        print(f"{s['source']:28} cov {s['coverage']['found']}/{s['coverage']['total']} acc {a['state'][:9]} {a['mean'] and round(a['mean'], 2)} "
              f"n={a['n']} wrong={a['n_wrong']} fresh median={f['median_days']} (n={f['n']}) ${s['usd']:.3f}")
