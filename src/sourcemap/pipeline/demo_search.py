"""Demo step 2–4: send the planner's queries to every Telem provider, pool candidate sources by
domain, blind review, and score providers (docs/plan/demo-samsung-marketing.md, ADR 0015).

Results are kept as JSON files under data/demo/ (a shortcut for today instead of the
search_* tables; logged as a deviation). Search hits are never evidence (R2).
"""

import csv
import io
import json
import random
from collections import defaultdict
from pathlib import Path

from sourcemap.measure.benchmark import KnownTrial, ProviderCall, provider_metrics, registrable_domain
from sourcemap.measure.benchmark import Candidate as BCandidate

PROVIDERS = ["brave", "exa", "tavily", "perplexity", "serpapi", "you", "parallel", "linkup", "tinyfish"]

# Sources we know hold this data, by host, and the planner category whose queries should find them.
KNOWN = {
    "dart": {"hosts": ("dart.fss.or.kr", "opendart.fss.or.kr"), "category_hint": "regulat"},
    "theorg": {"hosts": ("theorg.com",), "category_hint": "crowd"},
    "samsung.com": {"hosts": ("samsung.com", "news.samsung.com", "semiconductor.samsung.com"),
                    "category_hint": "own pages"},
}


def host_of(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0].split(":")[0].lower().removeprefix("www.")


def candidate_of(url: str) -> str:
    """Candidate source key: DART hosts kept whole, everything else by registrable domain."""
    host = host_of(url)
    for name, k in KNOWN.items():
        if any(host == h or host.endswith("." + h) for h in k["hosts"]):
            return name
    return registrable_domain(host)


def run_search(telem, plan: dict, out: Path, num_results: int = 5) -> dict:
    """Every query × every provider (pinned), plus Telem auto-routing. Saves data/demo/search.json."""
    rows = []
    qid = 0
    for cat in plan["categories"]:
        for q in cat["queries"]:
            qid += 1
            for routing, providers in [("pinned", PROVIDERS), ("auto", None)]:
                try:
                    res = telem.search(q, providers=providers, num_results=num_results)
                except Exception as e:  # one failing call never stops the run
                    rows.append({"qid": qid, "category": cat["name"], "query": q, "routing": routing,
                                 "error": str(e)[:300], "runs": []})
                    continue
                rows.append({"qid": qid, "category": cat["name"], "query": q, "routing": routing,
                             "runs": [{"provider": (r.provider if routing == "pinned" else f"auto:{r.provider}"),
                                       "status": r.status, "latency_ms": r.latency_ms, "usd": r.usd,
                                       "hits": [h.__dict__ for h in r.hits]} for r in res.runs]})
    data = {"plan": plan, "providers": PROVIDERS, "num_results": num_results, "rows": rows,
            "spent_usd": telem.spent_usd}
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    return data


def pool(search: dict) -> dict[str, dict]:
    """Candidates by key, remembering providers, ranks, queries and example URLs/titles."""
    cands: dict[str, dict] = {}
    for row in search["rows"]:
        for run in row["runs"]:
            for h in run["hits"]:
                key = candidate_of(h["url"])
                c = cands.setdefault(key, {"key": key, "providers": set(), "ranks": [], "qids": set(),
                                           "examples": []})
                c["providers"].add(run["provider"])
                c["ranks"].append((run["provider"], h["rank"]))
                c["qids"].add(row["qid"])
                if len(c["examples"]) < 3 and h["url"] not in [e[0] for e in c["examples"]]:
                    c["examples"].append((h["url"], h["title"], h["snippet"][:160]))
    return cands


def export_review(cands: dict, path: Path, cap: int = 40, seed: int = 7) -> int:
    """Blind review sheet: random order, no provider/rank/query columns. Known sources excluded."""
    keys = [k for k in cands if k not in KNOWN]
    # Review the candidates found most widely first, capped; the rest are 'not_sampled'.
    keys.sort(key=lambda k: -len(cands[k]["providers"]))
    sample = keys[:cap]
    random.Random(seed).shuffle(sample)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["candidate", "example_url", "example_title", "example_snippet", "decision (keep/reject)"])
    for k in sample:
        url, title, snip = cands[k]["examples"][0]
        w.writerow([k, url, title, snip, ""])
    path.write_text(buf.getvalue())
    return len(sample)


def leaderboard(search: dict, cands: dict, kept: set[str], reviewed: set[str]) -> list:
    """Provider metrics with the stage 1 benchmark rules (ADR 0015)."""
    providers = sorted({r["provider"] for row in search["rows"] for r in row["runs"]
                        if not r["provider"].startswith("auto:")}) + ["auto"]
    trials, calls = [], []
    for row in search["rows"]:
        expect = [n for n, k in KNOWN.items() if k["category_hint"] in row["category"].lower()]
        runs = row["runs"]
        if row["routing"] == "auto":  # auto-routing counts as one provider, "auto"
            hits = [h for r in runs for h in r["hits"]]
            runs = [{"provider": "auto", "status": "ok" if runs else "error", "latency_ms": None,
                     "usd": sum(r["usd"] for r in runs), "hits": sorted(hits, key=lambda h: h["rank"])}]
        for r in runs:
            calls.append(ProviderCall(r["provider"], r["status"] == "ok", r["usd"], r["latency_ms"]))
            for name in expect:
                ranks = [h["rank"] for h in r["hits"] if candidate_of(h["url"]) == name]
                trials.append(KnownTrial(r["provider"], bool(ranks), min(ranks) if ranks else None))
    bc = []
    for k, c in cands.items():
        provs = {p.removeprefix("auto:") if not p.startswith("auto:") else "auto" for p in c["providers"]}
        bc.append(BCandidate(k, c["examples"][0][0], frozenset(provs), tuple(c["ranks"]),
                             frozenset(c["qids"]), frozenset()))
    return provider_metrics(providers, trials, bc, set(KNOWN), kept, reviewed, calls)
