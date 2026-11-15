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
REF_DOMAINS = {"kr_listed": ["fss.or.kr"], "us_listed": ["sec.gov"], "us_mid": ["sec.gov"]}
# Every search provider Telem offered in the demo runs (data/demo/search.json); rows not yet run show as such.
PROVIDERS_ALL = ["brave", "exa", "linkup", "parallel", "perplexity", "serpapi", "tavily", "tinyfish", "you"]
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
        # product leadership from the reference (mid-size companies are asked about product)
        companies[slug]["department"] = c.get("department", "marketing")
        companies[slug]["ref_product"] = len(r.get("product_idx", []))
        companies[slug]["product_rows"] = [{"name": r["rows"][i]["name"], "title": r["rows"][i].get("title", ""),
                                            "role": r["rows"][i].get("responsibility", "")} for i in r.get("product_idx", [])]
        # top leadership from the reference, for the per-company graph on the Org chart page
        companies[slug]["top_rows"] = [{"name": x["name"], "title": x.get("title", ""), "role": x.get("responsibility", "")}
                                       for i, x in enumerate(r.get("rows", [])) if i in top_rows(c["segment"], r.get("rows", []))]
        _en = load(DEMO / "people_en.json") if (DEMO / "people_en.json").exists() else {}
        for row in companies[slug]["top_rows"] + companies[slug]["marketing_rows"]:
            if row["name"] in _en:  # Korean name → English (source spelling or romanized*)
                row["en"], row["en_from"] = _en[row["name"]]["en"], _en[row["name"]]["en_from"]

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

    # --- provider library (Telem benchmark) ----------------------------------------------------------------
    # A "good find" is a (source, company) pair worth reading: a source that made the library for that company,
    # or the company's official reference (DART · SEC · own site). Per provider and segment (and "all"):
    #   coverage  = good finds it returned / good finds returned by any provider (pooled recall)
    #   accuracy  = its results that point to a good find / all its results (precision)
    #   reference = calls whose results include the official reference
    #   cost      = $ per call and $ per good find; latency = median per call; failed = calls that errored
    good_src = {(s["key"], c) for s in sources for c in s["companies"]}
    blank = lambda: {"calls": 0, "failed": 0, "usd": 0.0, "lat": [], "results": 0, "good_results": 0,
                     "ref_hits": 0, "found": set()}
    prov = defaultdict(blank)
    for row in search["rows"]:
        slug = row["company"]
        seg = S.COMPANIES[slug]["segment"]
        ref_domains = REF_DOMAINS.get(seg) or S.COMPANIES[slug]["own_domains"]
        is_ref = lambda u: any(M.host(u) == d or M.host(u).endswith("." + d) for d in ref_domains)
        runs = row["runs"]
        if row["routing"] == "auto" and runs:  # auto-routing is one call that may return several provider blocks
            runs = [{"provider": "auto", "status": "ok" if any(r.get("status", "ok") == "ok" for r in runs) else "error",
                     "usd": sum(r["usd"] for r in runs), "latency_ms": max((r["latency_ms"] or 0) for r in runs) or None,
                     "hits": [h for r in runs for h in r["hits"]]}]
        for run in runs:
            for key in ((run["provider"], seg), (run["provider"], "all")):
                p = prov[key]
                p["calls"] += 1
                p["failed"] += run.get("status", "ok") != "ok"
                p["usd"] += run["usd"]
                if run["latency_ms"]:
                    p["lat"].append(run["latency_ms"])
                p["ref_hits"] += any(is_ref(h["url"]) for h in run["hits"])
                for h in run["hits"]:
                    p["results"] += 1
                    pair = ("REF", slug) if is_ref(h["url"]) else (M.source_key(h["url"]), slug)
                    if pair[0] == "REF" or pair in good_src:
                        p["good_results"] += 1
                        p["found"].add(pair)
    pooled = defaultdict(set)
    for (_, seg), x in prov.items():
        pooled[seg] |= x["found"]
    # exclusive finds: good finds that exactly one individual provider returned (auto-routing excluded)
    finders = defaultdict(lambda: defaultdict(set))
    for (name, seg), x in prov.items():
        if name != "auto":
            for pair in x["found"]:
                finders[seg][pair].add(name)
    run_names = {p for p, _ in prov}
    everyone = sorted(set(PROVIDERS_ALL) | run_names - {"auto"}) + ["auto"]
    provider_lib = []
    for p in everyone:
        r = {"provider": p, "run": p in run_names, "segments": {}}
        # a provider whose links are search-engine redirects (e.g. google.com/goto?url=<token>) can't be scored:
        # the real page is hidden, so its results never match a source. Flag it instead of ranking it at 0%.
        hosts = [M.host(h["url"]) for row in search["rows"] for run in row["runs"] if run["provider"] == p for h in run["hits"]]
        if hosts and sum(hh.endswith("google.com") for hh in hosts) / len(hosts) > 0.8:
            r["unscorable"] = "its links came back as Google redirects (google.com/goto) that hide the real page"
        for seg in list(S.SEGMENTS) + ["all"]:
            x = prov.get((p, seg))
            if not x or not x["calls"]:
                continue
            ok_calls = x["calls"] - x["failed"]
            n_found = len(x["found"])
            r["segments"][seg] = {
                "coverage": interval(n_found, len(pooled[seg])),
                "accuracy": interval(x["good_results"], x["results"]),
                "reference_found": interval(x["ref_hits"], ok_calls),
                "good_finds": n_found,
                "exclusive": sum(1 for f in finders[seg].values() if f == {p}) if p != "auto" else None, "results": x["results"], "calls": x["calls"], "failed": x["failed"],
                "usd": x["usd"], "usd_per_call": x["usd"] / x["calls"],
                "usd_per_find": x["usd"] / n_found if n_found else None,
                "latency_s": statistics.median(x["lat"]) / 1000 if x["lat"] else None}
        provider_lib.append(r)
    pool_sizes = {seg: len(v) for seg, v in pooled.items()}

    # --- the Samsung marketing answer (from the DART reference) --------------------------------------------
    dart = load(DEMO / "dart_execs.json")
    doc = load(DEMO / "dart_doc.json")
    units = defaultdict(list)
    for r in dart["marketing"]:
        m = re.match(r"(.*?(?:마케팅실|마케팅팀|마케팅센터))", r["responsibility"])
        units[m.group(1) if m else r["responsibility"]].append(
            {"name": r["name"], "rank": r["title"], "role": r["responsibility"],
             "head": r["responsibility"].endswith("장") and "담당임원" not in r["responsibility"]})
    en = load(DEMO / "people_en.json") if (DEMO / "people_en.json").exists() else {}
    li = load(DEMO / "people_linkedin_strict.json") if (DEMO / "people_linkedin_strict.json").exists() else {}
    for u in units.values():
        for x in u:
            x["en"] = en.get(x["name"], {}).get("en", "")
            x["en_from"] = en.get(x["name"], {}).get("en_from", "")
            x["linkedin"] = (li.get(x["name"]) or {}).get("url")
    samsung_answer = {"source": "DART", "url": doc["viewer_url"], "rcept_no": doc["rcept_no"], "sha": doc["sha256"][:16],
                      "units": [{"unit": u, "people": sorted(p, key=lambda x: (not x["head"], {"사장": 0, "부사장": 1, "상무": 2}.get(x["rank"], 9)))}
                                for u, p in sorted(units.items(), key=lambda kv: -len(kv[1]))]}
    old_search = load(DEMO / "search.json")

    sig = _signals()
    data_types = [
        {"slug": "org_chart", "name": "Org chart", "status": "measured",
         "what": "Who holds which role, with which title, reporting to whom.",
         "claims": ["employment", "title", "reports_to"]},
        {"slug": "leadership_signals", "name": "Leadership-change signals", "status": "measured" if sig else "designed",
         "scope": "US mega-cap only",
         "what": "Appointments and departures, and how late each source reports them.",
         "claims": ["appointed", "departed", "date"], "plan": "Reference: SEC 8-K Item 5.02 filings (US mega-cap); "
         "metrics: accuracy, coverage and freshness (days after the filing)."},
        {"slug": "technographics", "name": "Technographics", "status": "designed",
         "what": "Which tools and products a company uses.",
         "claims": ["uses tool", "since"], "plan": "Reference: our own fingerprint scan of the company's site, saved raw; "
         "metrics: recall of verified tools, confirmed share, cost. Absence of detection is never 'wrong'."},
    ]
    return {
        "measured_on": "2026-11-14", "data_types": data_types,
        "segments": S.SEGMENTS, "companies": companies, "library": library, "providers": provider_lib, "provider_pool": pool_sizes,
        "plans": {g: [{"name": c["name"], "queries": c["queries"][:2]} for c in plans[g]["categories"]] for g in S.SEGMENTS},
        "samsung_answer": samsung_answer,
        "marketing_depth": load(SEG / "marketing_depth.json") if (SEG / "marketing_depth.json").exists() else {},
        "samsung_tree": _tree(),
        "signals": sig,
        "stats": {"telem_calls": len(search["rows"]) + len(old_search["rows"]), "telem_usd": search["spent_usd"] + old_search["spent_usd"],
                  "seg_calls": len(search["rows"]), "seg_usd": search["spent_usd"], "n_sources": len(sources),
                  "n_companies": len(companies), "model_usd": sum(e.get("extract_usd", 0) + e.get("verify_usd", 0) for e in verified)},
    }


def _signals():
    """Leadership-change signals (data/sig), or None when they haven't been measured yet."""
    if (ROOT / "data/sig2/refs.json").exists() and any((ROOT / "data/sig2" / f).exists() for f in ("checks_articles.json", "checks_archive.json")):
        from sourcemap.pipeline.sig2_measure import build as sig2_build  # v2: fixed sources × every filed change
        return sig2_build(ROOT)
    if not ((ROOT / "data/sig/refs.json").exists() and (ROOT / "data/sig/reads.json").exists()):
        return None
    from sourcemap.pipeline.sig_measure import build as sig_build
    return sig_build(ROOT)


def _tree():
    import importlib.util
    spec = importlib.util.spec_from_file_location("samsung_tree", ROOT / "scripts/samsung_tree.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.build(ROOT)


def main():
    data = build()
    dist = WEB / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    for f in ("index.html", "style.css", "dartchart.css", "dartchart.js", "signals.js", "mktchart.css", "mktchart.js", "app.js"):
        shutil.copy(WEB / f, dist / f)
    (dist / "data.js").write_text("window.SOURCEMAP = " + json.dumps(data, ensure_ascii=False, default=list) + ";\n")
    print((dist / "index.html").resolve())


if __name__ == "__main__":
    main()
