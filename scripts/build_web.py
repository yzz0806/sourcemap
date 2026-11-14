"""Builds the frontend's data file from today's results (no network, no keys).

Reads data/seg (segment benchmark), data/demo (Samsung marketing demo) and writes
web/dist/{index.html, style.css, app.js, data.js}. Open web/dist/index.html in a browser.
"""

import json
import re
import shutil
import statistics
from collections import defaultdict
from pathlib import Path

from sourcemap.measure.accuracy import beta_interval
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import demo_segments as S

ROOT = Path(__file__).resolve().parents[1]
SEG, DEMO, WEB = ROOT / "data/seg", ROOT / "data/demo", ROOT / "web"
REF_DOMAINS = {"kr_listed": ["fss.or.kr"], "us_listed": ["sec.gov"]}
TOP_KR = {"회장", "부회장", "사장", "대표이사", "사내이사", "사외이사", "이사", "기타비상무이사"}


def load(p):
    return json.loads(Path(p).read_text())


def interval(num, den):
    if not den:
        return None
    iv = beta_interval(1 + num, 1 + den - num)
    return {"num": num, "den": den, "mean": num / den, "lo": iv.lo, "hi": iv.hi,
            "state": "measured" if den >= 5 else "not_enough_data"}


def top_rows(seg, rows):
    if seg == "kr_listed":
        return {i for i, r in enumerate(rows) if r.get("title") in TOP_KR}
    return set(range(len(rows)))


def build():
    refs, plans, search, verified = (load(SEG / f) for f in ("refs.json", "plans.json", "search.json", "verified.json"))
    sources = load(SEG / "sources.json")
    scost = M.search_cost_by_source(search)

    # --- companies & references --------------------------------------------------------------------
    companies = {}
    for slug, c in S.COMPANIES.items():
        r = refs.get(slug, {})
        companies[slug] = {"name": c["name"], "segment": c["segment"], "ref_kind": r.get("kind", "none"),
                           "ref_tier": r.get("tier"), "ref_url": r.get("url", ""), "ref_failed": r.get("failed", ""),
                           "ref_size": len(r.get("rows", [])), "ref_marketing": len(r.get("marketing_idx", [])),
                           "ref_located_by_telem": slug in ("sap", "siemens", "airbus"),
                           "marketing_rows": [{"name": r.get("rows", [])[i]["name"], "title": r["rows"][i].get("title", ""),
                                               "role": r["rows"][i].get("responsibility", "")}
                                              for i in r.get("marketing_idx", [])] if slug != "samsung-electronics" else []}

    # --- source library: source × segment ---------------------------------------------------------------
    cells = defaultdict(lambda: {"checks": [], "usd": 0.0, "reads": defaultdict(int), "top_found": set(),
                                 "top_total": 0, "mk_found": set(), "pairs": []})
    seg_top_total = defaultdict(int)
    for slug, c in S.COMPANIES.items():
        seg_top_total[c["segment"]] += len(top_rows(c["segment"], refs.get(slug, {}).get("rows", [])))
    for e in verified:
        k, slug, seg = e["source"], e["company"], e["segment"]
        x = cells[(k, seg)]
        x["usd"] += scost.get((k, slug), 0) + e.get("extract_usd", 0) + e.get("verify_usd", 0)
        st = e["status"] if e["status"] in ("ok", "not_found") else "blocked"
        if st == "ok" and not e.get("people"):
            st = "empty"
        x["reads"][st] += 1
        rows = refs.get(slug, {}).get("rows", [])
        tops, mks = top_rows(seg, rows), set(refs.get(slug, {}).get("marketing_idx", []))
        for ch in e.get("checks", []):
            x["checks"].append(ch)
            if ch["ref_index"] in tops:
                x["top_found"].add((slug, ch["ref_index"]))
            if ch["ref_index"] in mks:
                x["mk_found"].add((slug, ch["ref_index"]))
        pair_usd = scost.get((k, slug), 0) + e.get("extract_usd", 0) + e.get("verify_usd", 0)
        x["pairs"].append({"company": slug, "status": e["status"], "url": e.get("url"), "sha": e.get("sha256", "")[:16],
                           "usd": pair_usd, "n_people": len(e.get("people", [])),
                           "checks": [{"name": ch["person"]["name"], "title": ch["person"]["title"],
                                       "quote": ch["person"].get("quote", "")[:180], "ref": ch["ref_quote"],
                                       "employment": ch["employment"], "verdict": ch["title"], "reason": ch["reason"][:200]}
                                      for ch in e.get("checks", [])]})
    library = []
    for s in sources:
        k = s["key"]
        tier = M.tier_of(k, {"own_domains": []})
        row = {"source": k, "tier": int(tier), "segments": {}}
        for seg in S.SEGMENTS:
            x = cells[(k, seg)]
            sc = M.score(x["checks"], tier)
            mk_total = sum(companies[c]["ref_marketing"] for c in companies if companies[c]["segment"] == seg)
            row["segments"][seg] = {
                "title": sc["title"], "employment": sc["employment"],
                "coverage": {"found": len(x["top_found"]), "total": seg_top_total[seg]},
                "marketing": {"found": len(x["mk_found"]), "total": mk_total},
                "reads": dict(x["reads"]), "usd": x["usd"], "pairs": x["pairs"]}
        library.append(row)

    # --- provider library (Telem benchmark), per segment ---------------------------------------------------
    picked = {s["key"] for s in sources}
    prov = defaultdict(lambda: {"calls": 0, "usd": 0.0, "lat": [], "ref_trials": 0, "ref_hits": 0, "found": set()})
    for row in search["rows"]:
        seg = S.COMPANIES[row["company"]]["segment"]
        ref_domains = REF_DOMAINS.get(seg) or S.COMPANIES[row["company"]]["own_domains"]
        runs = row["runs"]
        if row["routing"] == "auto" and runs:  # auto-routing is one call that may return several provider blocks
            runs = [{"provider": "auto", "usd": sum(r["usd"] for r in runs),
                     "latency_ms": max((r["latency_ms"] or 0) for r in runs) or None,
                     "hits": [h for r in runs for h in r["hits"]]}]
        for run in runs:
            p = prov[(run["provider"], seg)]
            p["calls"] += 1
            p["usd"] += run["usd"]
            if run["latency_ms"]:
                p["lat"].append(run["latency_ms"])
            hosts = [M.host(h["url"]) for h in run["hits"]]
            p["ref_trials"] += 1
            p["ref_hits"] += any(any(hh == d or hh.endswith("." + d) for d in ref_domains) for hh in hosts)
            for h in run["hits"]:
                if M.source_key(h["url"]) in picked:
                    p["found"].add((M.source_key(h["url"]), row["company"]))
    providers = sorted({p for p, _ in prov})
    provider_lib = []
    for p in providers:
        r = {"provider": p, "segments": {}}
        for seg in S.SEGMENTS:
            x = prov.get((p, seg))
            if not x:
                continue
            r["segments"][seg] = {"reference_found": interval(x["ref_hits"], x["ref_trials"]),
                                  "pairs_found": len(x["found"]), "usd": x["usd"], "calls": x["calls"],
                                  "latency_s": statistics.median(x["lat"]) / 1000 if x["lat"] else None}
        provider_lib.append(r)

    # --- the Samsung marketing answer (from the DART reference) --------------------------------------------
    dart = load(DEMO / "dart_execs.json")
    doc = load(DEMO / "dart_doc.json")
    units = defaultdict(list)
    for r in dart["marketing"]:
        m = re.match(r"(.*?(?:마케팅실|마케팅팀|마케팅센터))", r["responsibility"])
        units[m.group(1) if m else r["responsibility"]].append(
            {"name": r["name"], "rank": r["title"], "role": r["responsibility"],
             "head": r["responsibility"].endswith("장") and "담당임원" not in r["responsibility"]})
    samsung_answer = {"source": "DART", "url": doc["viewer_url"], "rcept_no": doc["rcept_no"], "sha": doc["sha256"][:16],
                      "units": [{"unit": u, "people": sorted(p, key=lambda x: (not x["head"], {"사장": 0, "부사장": 1, "상무": 2}.get(x["rank"], 9)))}
                                for u, p in sorted(units.items(), key=lambda kv: -len(kv[1]))]}
    old_search = load(DEMO / "search.json")

    data_types = [
        {"slug": "org_chart", "name": "Org chart", "status": "measured",
         "what": "Who holds which role, with which title, reporting to whom.",
         "claims": ["employment", "title", "reports_to"]},
        {"slug": "technographics", "name": "Technographics", "status": "designed",
         "what": "Which tools and products a company uses.",
         "claims": ["uses tool", "since"], "plan": "Reference: our own fingerprint scan of the company's site, saved raw; "
         "metrics: recall of verified tools, confirmed share, cost. Absence of detection is never 'wrong'."},
        {"slug": "leadership_signals", "name": "Leadership-change signals", "status": "designed",
         "what": "Appointments and departures, and how late each source reports them.",
         "claims": ["appointed", "departed", "date"], "plan": "References: SEC 8-K Item 5.02, DART executive-change "
         "disclosures; metrics: accuracy, coverage and freshness (days late)."},
    ]
    return {
        "measured_on": "2026-11-14", "data_types": data_types,
        "segments": S.SEGMENTS, "companies": companies, "library": library, "providers": provider_lib,
        "plans": {g: [{"name": c["name"], "queries": c["queries"][:2]} for c in plans[g]["categories"]] for g in S.SEGMENTS},
        "samsung_answer": samsung_answer,
        "stats": {"telem_calls": len(search["rows"]) + len(old_search["rows"]), "telem_usd": search["spent_usd"] + old_search["spent_usd"],
                  "seg_calls": len(search["rows"]), "seg_usd": search["spent_usd"], "n_sources": len(sources),
                  "n_companies": len(companies), "model_usd": sum(e.get("extract_usd", 0) + e.get("verify_usd", 0) for e in verified)},
    }


def main():
    data = build()
    dist = WEB / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for f in ("index.html", "style.css", "app.js"):
        shutil.copy(WEB / f, dist / f)
    (dist / "data.js").write_text("window.SOURCEMAP = " + json.dumps(data, ensure_ascii=False, default=list) + ";\n")
    print((dist / "index.html").resolve())


if __name__ == "__main__":
    main()
