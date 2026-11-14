"""Segment-level marketing org-chart benchmark, step by step; each step caches in data/seg/.

  .venv/bin/python scripts/demo_segments.py plan     # one planner call per segment (query templates)
  .venv/bin/python scripts/demo_segments.py search   # Telem: every company's queries × providers + auto
  .venv/bin/python scripts/demo_segments.py read     # pick sources, fetch raw, extract people (quotes checked)
  .venv/bin/python scripts/demo_segments.py verify   # match to the segment reference (data/seg/refs.json)
References: scripts/demo_refs.py. Page: scripts/demo_segments_page.py.
"""

import json
import sys
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import demo_segments as S
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM, PLANNER_MODEL
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/seg")
D.mkdir(parents=True, exist_ok=True)
ENV = load_env(Path(".env"))
RAW = RawStore("data/raw")
KIT = Kit(min_interval_s=1.0, max_retries=2, timeout_s=40)
QUERIES_PER_COMPANY = 8


def save(n, o):
    (D / n).write_text(json.dumps(o, ensure_ascii=False, indent=1, default=str))


def load(n):
    return json.loads((D / n).read_text())


def llm(b):
    return LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=b)


def step_plan():
    L = llm(0.3)
    plans = {}
    for seg, info in S.SEGMENTS.items():
        names = [c["name"] for c in S.COMPANIES.values() if c["segment"] == seg]
        q = f"Segment: {info['name']} ({info['country']}). Example companies: {', '.join(names)}."
        plans[seg] = L.ask_json(PLANNER_MODEL, "plan_segment/v1", S.PLAN_PROMPT, q)
        print(seg, [c["name"] for c in plans[seg]["categories"]])
    print(f"planner ${L.spent_usd:.3f}")
    save("plans.json", plans)


def company_queries(plan, c):
    out = []
    for cat in plan["categories"]:
        for t in cat["queries"][:2]:
            out.append((cat["name"], t.replace("{company}", c["name"]).replace("{company_local}", c["name_local"])))
    # round-robin over categories so each category is represented within the cap
    by_cat = {}
    for cat, q in out:
        by_cat.setdefault(cat, []).append(q)
    rr, i = [], 0
    while len(rr) < min(QUERIES_PER_COMPANY, len(out)):
        for cat, qs in by_cat.items():
            if i < len(qs) and len(rr) < QUERIES_PER_COMPANY:
                rr.append((cat, qs[i]))
        i += 1
    return rr


def step_search():
    plans = load("plans.json")
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=3.0)
    rows = []
    for slug, c in S.COMPANIES.items():
        for cat, q in company_queries(plans[c["segment"]], c):
            for routing, provs in (("pinned", M.PROVIDERS), ("auto", None)):
                try:
                    res = t.search(q, providers=provs, num_results=5)
                except Exception as e:
                    rows.append({"company": slug, "category": cat, "query": q, "routing": routing, "error": str(e)[:200], "runs": []})
                    continue
                rows.append({"company": slug, "category": cat, "query": q, "routing": routing,
                             "runs": [{"provider": r.provider if routing == "pinned" else "auto", "status": r.status,
                                       "latency_ms": r.latency_ms, "usd": r.usd, "hits": [h.__dict__ for h in r.hits]}
                                      for r in res.runs]})
        print(slug, "spent", round(t.spent_usd, 3))
    save("search.json", {"providers": M.PROVIDERS, "rows": rows, "spent_usd": t.spent_usd})


def step_read(top=10):
    search = load("search.json")
    sources = M.pick_sources(search, min_companies=3, top=top, companies=S.COMPANIES)
    L = llm(1.0)
    reads = []
    for s in sources:
        for slug, c in S.COMPANIES.items():
            url = s["urls"].get(slug)
            e = {"source": s["key"], "company": slug, "segment": c["segment"], "url": url}
            if not url:
                e["status"] = "not_found"
            else:
                try:
                    r = KIT.get(url)
                    sha = RAW.put(r.body)
                    ctype = r.headers.get("Content-Type", r.headers.get("content-type", "html"))
                    if r.status != 200 or "html" not in ctype:
                        e.update(status=f"failed: HTTP {r.status}", sha256=sha)
                    else:
                        text = M.html_to_text(r.text())
                        before = L.spent_usd
                        ans = L.ask_json(JUDGE_MODEL, "extract_people/v1", M.EXTRACT_PROMPT.format(company=c["name"]),
                                         text, max_tokens=8000)
                        tn = M.norm(text)
                        people = [p for p in ans.get("people", []) if M.quote_ok(p, tn)]
                        e.update(status="ok", sha256=sha, people=people,
                                 dropped_unquoted=len(ans.get("people", [])) - len(people), extract_usd=L.spent_usd - before)
                except BlockedByRobots:
                    e["status"] = "blocked_by_robots"
                except (FetchError, OSError) as ex:
                    e["status"] = f"failed: {type(ex).__name__}"
            reads.append(e)
            print(s["key"], slug, e["status"], len(e.get("people", [])))
    print(f"extraction ${L.spent_usd:.3f}")
    save("sources.json", sources)
    save("reads.json", reads)


def step_verify():
    refs, reads = load("refs.json"), load("reads.json")
    L = llm(2.0)
    out = []
    for e in reads:
        ref = refs.get(e["company"])
        if e.get("status") != "ok" or not e.get("people") or not ref or not ref.get("rows"):
            out.append({**e, "checks": [], "verify_usd": 0.0})
            continue
        rows = ref["rows"]
        a = "\n".join(f"{i}\t{p['name']}\t{p['title']}" for i, p in enumerate(e["people"]))
        b = "\n".join(f"{i}\t{r['name']}\t{r['title']}\t{r.get('responsibility', '')}" for i, r in enumerate(rows))
        before = L.spent_usd
        ans = L.ask_json(PLANNER_MODEL, "match_multi/v1",
                         M.MATCH_PROMPT.format(company=S.COMPANIES[e["company"]]["name"], ref_desc=ref["kind"]),
                         f"List A (index, name, title):\n{a}\n\nList B (index, name, rank/title, responsibility):\n{b}",
                         max_tokens=8000)
        checks = M.verdicts(e["people"], rows, ans.get("matches", []), False)
        out.append({**e, "checks": checks, "verify_usd": L.spent_usd - before})
        print(e["source"], e["company"], sum(c["employment"] == "correct" for c in checks), "/", len(checks))
    print(f"verify ${L.spent_usd:.3f}")
    save("verified.json", out)


if __name__ == "__main__":
    {"plan": step_plan, "search": step_search, "read": step_read, "verify": step_verify}[sys.argv[1]]()
