"""Leadership-change signals v2: a fixed set of sources, each checked against every filed change.

Reference: data/sig2/refs.json (8-K Item 5.02, 10 US mega-caps, 5 years). Checks, one per (filed change ×
source): data/sig2/checks_articles.json (newsroom, wires, Reuters, CNBC — located with Telem site-restricted
search, page read) and data/sig2/checks_archive.json (Wikipedia revision history; Wayback snapshots of Yahoo
Finance, MarketScreener, theorg). Each check: {event_id, company, source, status, verdict, date, days_late,
url, evidence, quote, usd}; status ∈ found | not_found | blocked | not_tracked | error.

Per source: coverage = changes it reflected / changes it could have (not_tracked excluded); accuracy = Beta
over decisive verdicts (correct / wrong; a miss is a coverage gap, not an error); freshness = days between
the 8-K filing and the source's publication or first snapshot showing the change; cost.
The output keeps the shape web/signals.js reads (sources, timeline, total_ref_events…).
"""

import json
import statistics
from collections import defaultdict
from datetime import date
from pathlib import Path

from sourcemap.domain.model import Verification
from sourcemap.domain.vocab import Method, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for

T0 = date(2026, 11, 14)
TIER = {"newsroom": Tier.FIRST_PARTY, "wikipedia.org": Tier.RESEARCHED, "theorg.com": Tier.RESEARCHED}
KIND = {"newsroom": "company's own", "businesswire.com": "wire", "prnewswire.com": "wire", "reuters.com": "news",
        "cnbc.com": "news", "stocktitan.net": "wire mirror", "apnews.com": "news", "bloomberg.com": "news",
        "foxbusiness.com": "news", "fortune.com": "news", "businessinsider.com": "news", "nytimes.com": "news",
        "techcrunch.com": "tech news", "theverge.com": "tech news", "wikipedia.org": "encyclopedia (revision history)", "finance.yahoo.com": "officer list (Wayback)",
        "marketscreener.com": "officer list (Wayback)", "theorg.com": "org-chart site (Wayback)"}


def build(root: Path) -> dict:
    refs = json.loads((root / "data/sig2/refs.json").read_text())
    checks = []
    for f in ("checks_articles.json", "checks_archive.json"):
        p = root / "data/sig2" / f
        if p.exists():
            checks += json.loads(p.read_text())
    events = {e["id"]: e for e in refs["events"]}

    per = defaultdict(lambda: {"checks": [], "usd": 0.0})
    by_event = defaultdict(list)
    for c in checks:
        if c["event_id"] not in events:
            continue
        per[c["source"]]["checks"].append(c)
        per[c["source"]]["usd"] += c.get("usd") or 0
        if c.get("verdict") == "correct":
            by_event[c["event_id"]].append({"source": c["source"], "url": c.get("evidence") or c.get("url"),
                                            "published": c.get("date"), "days_late": c.get("days_late")})

    sources = []
    for src, s in per.items():
        cs = s["checks"]
        applicable = [c for c in cs if c["status"] not in ("not_tracked",)]
        found = [c for c in cs if c.get("verdict") == "correct"]
        vs = [Verification(i, Method.REFERENCE, Verdict(c["verdict"]), T0) for i, c in enumerate(cs) if c.get("verdict") in ("correct", "wrong")]
        e = estimate(vs, prior_for(TIER.get(src, Tier.AGGREGATE)))
        late = sorted(c["days_late"] for c in found if c.get("days_late") is not None)
        sources.append({
            "source": src, "kind": KIND.get(src, ""), "tier": int(TIER.get(src, Tier.AGGREGATE)),
            "pages": sum(1 for c in cs if c["status"] == "found"), "blocked": sum(1 for c in cs if c["status"] in ("blocked", "error")),
            "not_tracked": sum(1 for c in cs if c["status"] == "not_tracked"),
            "companies": sorted({c["company"] for c in found}),
            "accuracy": {"state": e.state.value, "mean": e.mean, "interval": [e.interval.lo, e.interval.hi] if e.interval else None,
                         "n": e.n_decisive, "n_wrong": e.n_wrong, "unverifiable_share": 0.0},
            "coverage": {"found": len(found), "total": len(applicable),
                         "mean": len(found) / len(applicable) if applicable else None},
            "freshness": {"median_days": statistics.median(late) if late else None, "n": len(late), "values": late,
                          # Wayback-measured pages: the change appeared somewhere between the last snapshot without it and
                          # the first with it — report the median width of that window (precision of the freshness number)
                          "median_bound_width": statistics.median([b[1] - b[0] for b in (c.get("bound_days") for c in found) if b and len(b) == 2])
                          if any(c.get("bound_days") for c in found) else None},
            "usd": s["usd"],
            "events": [{"company": c["company"], "person": events[c["event_id"]]["person"], "change": events[c["event_id"]]["change"],
                        "verdict": c.get("verdict") or "unverifiable", "days_late": c.get("days_late"), "url": c.get("url")} for c in cs],
        })
    sources.sort(key=lambda x: (-(x["coverage"]["mean"] or 0), -(x["accuracy"]["mean"] or 0)))
    timeline = sorted(({**ev, "reported_by": sorted(by_event.get(eid, []), key=lambda r: (r["days_late"] is None, r["days_late"] or 0))}
                       for eid, ev in events.items()), key=lambda e: e["filing_date"], reverse=True)
    companies = {slug: {"name": c.get("name", slug), "ticker": c.get("ticker", "")} for slug, c in refs["companies"].items()}
    return {"version": 2, "segment": "us_listed", "window": refs.get("window"), "total_ref_events": len(events),
            "companies": companies, "sources": sources, "timeline": timeline,
            "spent_usd": sum(s["usd"] for s in per.values())}


if __name__ == "__main__":
    root = Path(__file__).resolve().parents[3]
    out = build(root)
    (root / "data/sig2/measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    for s in out["sources"]:
        a, f, c = s["accuracy"], s["freshness"], s["coverage"]
        print(f"{s['source']:22} cov {c['found']}/{c['total']} acc {a['state'][:9]} {a['mean'] and round(a['mean'], 2)} n={a['n']} "
              f"wrong={a['n_wrong']} fresh median={f['median_days']} (n={f['n']}) ${s['usd']:.3f}")
