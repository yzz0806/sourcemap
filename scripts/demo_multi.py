"""Runs the multi-segment source benchmark step by step; each step caches its output in data/multi/.

  .venv/bin/python scripts/demo_multi.py refs     # references: DART (Samsung), own pages (Nvidia, Airbus)
  .venv/bin/python scripts/demo_multi.py plan     # planner per company (OpenRouter)
  .venv/bin/python scripts/demo_multi.py search   # Telem: every query × providers + auto
  .venv/bin/python scripts/demo_multi.py read     # pick sources, fetch pages raw, extract people
  .venv/bin/python scripts/demo_multi.py verify   # match to reference, verdicts, scores
"""

import json
import sys
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM, PLANNER_MODEL
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/multi")
D.mkdir(parents=True, exist_ok=True)
ENV = load_env(Path(".env"))
RAW = RawStore("data/raw")
KIT = Kit(min_interval_s=1.0, max_retries=2, timeout_s=40)


def save(name, obj):
    (D / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str))


def load(name):
    return json.loads((D / name).read_text())


def llm(budget=2.0):
    return LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=budget)


def fetch(url):
    r = KIT.get(url)
    sha = RAW.put(r.body)
    return r, sha


def extract(model_llm, company, text):
    before = model_llm.spent_usd
    ans = model_llm.ask_json(JUDGE_MODEL, "extract_people/v1", M.EXTRACT_PROMPT.format(company=company),
                             text, max_tokens=8000)
    people = ans.get("people", [])
    tn = M.norm(text)
    kept = [p for p in people if M.quote_ok(p, tn)]
    return kept, len(people) - len(kept), model_llm.spent_usd - before


def step_refs():
    refs = {}
    old = json.loads(Path("data/demo/dart_execs.json").read_text())
    doc = json.loads(Path("data/demo/dart_doc.json").read_text())
    refs["samsung-electronics"] = {"kind": "DART 2025 annual report (official filing, tier 1)",
                                   "url": doc["viewer_url"], "sha256": doc["sha256"], "complete": False,
                                   "rows": [{"name": r["name"], "title": r["title"], "responsibility": r["responsibility"]}
                                            for r in old["all"]]}
    L = llm(0.5)
    for slug in ("nvidia", "airbus"):
        c = M.COMPANIES[slug]
        r, sha = fetch(c["reference"])
        people, dropped, usd = extract(L, c["name"], M.html_to_text(r.text()))
        refs[slug] = {"kind": "company's own page (tier 2)", "url": c["reference"], "sha256": sha, "complete": False,
                      "rows": [{"name": p["name"], "title": p["title"], "responsibility": "", "quote": p["quote"]}
                               for p in people], "dropped_unquoted": dropped, "usd": usd}
        print(slug, len(people), "people (dropped", dropped, "without a quote on the page)", f"${usd:.4f}")
    save("refs.json", refs)


def step_plan():
    L = llm(0.5)
    plans = {}
    for slug, c in M.COMPANIES.items():
        q = f"Company: {c['name']} ({c['country']}). Segment: {c['segment']}. Find sources for its leadership / org chart."
        plans[slug] = L.ask_json(PLANNER_MODEL, "plan_company/v1", M.PLAN_PROMPT, q)
        print(slug, [x["name"] for x in plans[slug]["categories"]])
    print(f"planner ${L.spent_usd:.3f}")
    save("plans.json", plans)


def step_search(max_queries=12):
    plans = load("plans.json")
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=2.5)
    rows = []
    for slug, plan in plans.items():
        queries = [(cat["name"], q) for cat in plan["categories"] for q in cat["queries"][:2]][:max_queries]
        for cat, q in queries:
            for routing, provs in (("pinned", M.PROVIDERS), ("auto", None)):
                try:
                    res = t.search(q, providers=provs, num_results=5)
                except Exception as e:
                    rows.append({"company": slug, "category": cat, "query": q, "routing": routing, "error": str(e)[:200], "runs": []})
                    continue
                rows.append({"company": slug, "category": cat, "query": q, "routing": routing,
                             "runs": [{"provider": r.provider if routing == "pinned" else "auto",
                                       "status": r.status, "latency_ms": r.latency_ms, "usd": r.usd,
                                       "hits": [h.__dict__ for h in r.hits]} for r in res.runs]})
        print(slug, "done, spent so far", round(t.spent_usd, 3))
    save("search.json", {"providers": M.PROVIDERS, "rows": rows, "spent_usd": t.spent_usd})


def step_read():
    search = load("search.json")
    sources = M.pick_sources(search, top=9)
    L = llm(1.5)
    reads = []
    earlier = earlier_samsung_urls()
    for s in sources:
        for slug in M.COMPANIES:
            url = s["urls"].get(slug)
            entry = {"source": s["key"], "company": slug, "url": url, "url_from": "this search"}
            if not url and slug == "samsung-electronics" and s["key"] in earlier:
                url = entry["url"] = earlier[s["key"]]
                entry["url_from"] = "the earlier Samsung search (data/demo/search.json)"
            if not url:
                entry["status"] = "not_found"  # the search never returned this source for this company
            else:
                try:
                    r, sha = fetch(url)
                    if r.status != 200 or "html" not in r.headers.get("Content-Type", r.headers.get("content-type", "html")):
                        entry.update(status=f"failed: HTTP {r.status}", sha256=sha)
                    else:
                        people, dropped, usd = extract(L, M.COMPANIES[slug]["name"], M.html_to_text(r.text()))
                        entry.update(status="ok", sha256=sha, people=people, dropped_unquoted=dropped, extract_usd=usd)
                except BlockedByRobots:
                    entry["status"] = "blocked_by_robots"
                except (FetchError, OSError) as e:
                    entry["status"] = f"failed: {type(e).__name__}"
            reads.append(entry)
            print(s["key"], slug, entry["status"], len(entry.get("people", [])))
    print(f"extraction ${L.spent_usd:.3f}")
    save("sources.json", sources)
    save("reads.json", reads)


def earlier_samsung_urls():
    """Best Samsung URL per source from the first (Samsung-only) search, preferring 'samsung' URLs."""
    p = Path("data/demo/search.json")
    if not p.exists():
        return {}
    best = {}
    for row in json.loads(p.read_text())["rows"]:
        for run in row["runs"]:
            for h in run["hits"]:
                k, u = M.source_key(h["url"]), h["url"]
                if "samsung" not in u.lower() or u.lower().endswith(".pdf"):
                    continue
                # The shortest URL is the source's page for the company, not a sub-page about one person.
                if k not in best or (len(u), h["rank"]) < best[k][0]:
                    best[k] = ((len(u), h["rank"]), u)
    return {k: v[1] for k, v in best.items()}


def step_verify():
    refs, reads = load("refs.json"), load("reads.json")
    L = llm(1.5)
    out = []
    for e in reads:
        if e.get("status") != "ok" or not e.get("people"):
            out.append({**e, "checks": [], "verify_usd": 0.0})
            continue
        ref = refs[e["company"]]
        rows = ref["rows"]
        a = "\n".join(f"{i}\t{p['name']}\t{p['title']}" for i, p in enumerate(e["people"]))
        b = "\n".join(f"{i}\t{r['name']}\t{r['title']}\t{r.get('responsibility', '')}" for i, r in enumerate(rows))
        before = L.spent_usd
        ans = L.ask_json(PLANNER_MODEL, "match_multi/v1",
                         M.MATCH_PROMPT.format(company=M.COMPANIES[e["company"]]["name"], ref_desc=ref["kind"]),
                         f"List A (index, name, title):\n{a}\n\nList B (index, name, rank/title, responsibility):\n{b}",
                         max_tokens=8000)
        checks = M.verdicts(e["people"], rows, ans.get("matches", []), ref["complete"])
        out.append({**e, "checks": checks, "verify_usd": L.spent_usd - before})
        print(e["source"], e["company"], sum(c["employment"] == "correct" for c in checks), "/", len(checks), "matched")
    print(f"verify ${L.spent_usd:.3f}")
    save("verified.json", out)


if __name__ == "__main__":
    {"refs": step_refs, "plan": step_plan, "search": step_search, "read": step_read,
     "verify": step_verify}[sys.argv[1]]()
