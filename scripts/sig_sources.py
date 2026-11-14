"""Leadership-change signals, sources side: plan | search | read (each step cached in data/sig/).

  .venv/bin/python scripts/sig_sources.py plan|search|read
"""

import json
import sys
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import sig_sources as G
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM, PLANNER_MODEL
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/sig")
D.mkdir(parents=True, exist_ok=True)
ENV = load_env(Path(".env"))


def step_plan():
    out = D / "plan.json"
    if out.exists():
        print("plan cached"); return
    L = LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.2)
    plan = L.ask_json(PLANNER_MODEL, "sig_plan/v1", G.PLAN_PROMPT,
                      "Segment: US mega-cap (largest S&P 500 companies). Example companies: Nvidia, Apple, Microsoft. "
                      "Data type: leadership changes — executive appointments and departures, with dates.")
    out.write_text(G.dumps(plan))
    print("categories:", [c["name"] for c in plan["categories"]], f"cost ${L.spent_usd:.3f}")


def queries(plan, company, n=10):
    by = [(c["name"], [q.replace("{company}", company) for q in c["queries"][:2]]) for c in plan["categories"]]
    out, i = [], 0
    while len(out) < n and any(i < len(qs) for _, qs in by):
        for cat, qs in by:
            if i < len(qs) and len(out) < n:
                out.append((cat, qs[i]))
        i += 1
    return out


def step_search():
    out = D / "search.json"
    if out.exists():
        print("search cached"); return
    plan = json.loads((D / "plan.json").read_text())
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=1.6)
    rows = []
    for slug, name in G.COMPANIES.items():
        for cat, q in queries(plan, name):
            for routing, provs in (("pinned", G.PROVIDERS), ("auto", None)):
                try:
                    res = t.search(q, providers=provs, num_results=5)
                except Exception as e:  # noqa: BLE001
                    rows.append({"company": slug, "category": cat, "query": q, "routing": routing, "error": str(e)[:200], "runs": []})
                    continue
                rows.append({"company": slug, "category": cat, "query": q, "routing": routing,
                             "runs": [{"provider": r.provider if routing == "pinned" else "auto", "status": r.status,
                                       "latency_ms": r.latency_ms, "usd": r.usd, "hits": [h.__dict__ for h in r.hits]}
                                      for r in res.runs]})
        print(slug, "spent", round(t.spent_usd, 3))
    out.write_text(G.dumps({"providers": G.PROVIDERS, "rows": rows, "spent_usd": t.spent_usd}))
    print(f"search ${t.spent_usd:.3f}, errors {sum(1 for r in rows if r.get('error'))}")


def step_read():
    search = json.loads((D / "search.json").read_text())
    prev = {(r["company"], r["url"]): r for r in json.loads((D / "reads.json").read_text())} if (D / "reads.json").exists() else {}
    kit = Kit(min_interval_s=1.0, max_retries=2, timeout_s=30)
    raw = RawStore("data/raw")
    L = LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.6)
    reads = []
    for slug, name in G.COMPANIES.items():
        for item in G.pick_urls(search["rows"], slug):
            url = item["url"]
            if (slug, url) in prev and prev[(slug, url)]["status"] in ("ok", "blocked_by_robots") or (slug, url) in prev and prev[(slug, url)]["status"].startswith("failed: HTTP"):
                reads.append(prev[(slug, url)]); continue
            e = {"company": slug, "url": url, "source": M.source_key(url), "found_by": item["found_by"], "events": [],
                 "extract_usd": 0.0, "sha256": None, "published": None, "published_from": None}
            try:
                r = kit.get(url)
                e["sha256"] = raw.put(r.body)
                ctype = r.headers.get("Content-Type", r.headers.get("content-type", "html"))
                if r.status != 200 or "html" not in ctype:
                    e["status"] = f"failed: HTTP {r.status}" if r.status != 200 else "failed: not HTML"
                else:
                    html = r.text()
                    e["published"], e["published_from"] = G.published(html)
                    text = M.html_to_text(html, limit=15000)
                    before = L.spent_usd
                    ans = L.ask_json(JUDGE_MODEL, "sig_src_extract/v1", G.EXTRACT_PROMPT.format(company=name), text, max_tokens=3000)
                    tn = G.norm(text)
                    evs = ans.get("events", []) if isinstance(ans, dict) else []
                    e["events"] = [ev for ev in evs if G.event_ok(ev, tn)]
                    e["dropped_unquoted"] = len(evs) - len(e["events"])
                    e["extract_usd"] = L.spent_usd - before
                    e["status"] = "ok"
            except BlockedByRobots:
                e["status"] = "blocked_by_robots"
            except (FetchError, OSError) as ex:
                e["status"] = f"failed: {type(ex).__name__}"
            except Exception as ex:  # noqa: BLE001 — a bad model answer never stops the run
                e["status"] = f"failed: {type(ex).__name__}: {str(ex)[:80]}"
            reads.append(e)
        print(slug, "done", f"extract so far ${L.spent_usd:.3f}")
        (D / "reads.json").write_text(G.dumps(reads))
    (D / "reads.json").write_text(G.dumps(reads))
    print(f"extraction ${L.spent_usd:.3f}")


if __name__ == "__main__":
    {"plan": step_plan, "search": step_search, "read": step_read}[sys.argv[1]]()
