"""Add mid-size companies to the segment benchmark for PRODUCT leadership, end to end.

  .venv/bin/python scripts/demo_add_companies.py ref      # official reference per company → refs.json
  .venv/bin/python scripts/demo_add_companies.py plan     # planner: product-department query templates per new segment
  .venv/bin/python scripts/demo_add_companies.py search   # Telem: 8 queries × every scorable provider + auto-routing
  .venv/bin/python scripts/demo_add_companies.py read     # pick sources per company, fetch raw, extract people (quotes checked)
  .venv/bin/python scripts/demo_add_companies.py verify   # match people to the reference
  .venv/bin/python scripts/demo_add_companies.py all

Companies (pipeline/demo_segments.py):
  sprinklr — US mid-cap · reference: SEC DEF 14A executive officers (tier 1; names the Chief Product Officer)
  typeform — European mid-size, private · reference: typeform.com/about-us leadership team (tier 2)
Everything is appended to the data/seg files the site is built from; each file is copied to
<name>.before_add.json the first time. Re-running a step replaces only these companies' entries.
Search results only find sources (R2); every extracted person must quote text found on the saved page.
"""

import json
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import demo_refs as R
from sourcemap.pipeline import demo_segments as S
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM, PLANNER_MODEL
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/seg")
ENV = load_env(Path(".env"))
RAW = RawStore("data/raw")
KIT = Kit(min_interval_s=1.0, max_retries=2, timeout_s=40)
SEC = Kit(min_interval_s=0.3, max_retries=2, timeout_s=60, user_agent=ENV.get("SEC_USER_AGENT", ""))
NEW = ["sprinklr", "typeform"]
PROVIDERS = ["brave", "exa", "linkup", "parallel", "perplexity", "tavily", "tinyfish", "you"]  # serpapi: links unscorable
QUERIES_PER_COMPANY = 8
SOURCES_PER_COMPANY = 8
SPRINKLR_CIK = 1569345


def load(n):
    return json.loads((D / n).read_text())


def save(n, o):
    p = D / n
    backup = p.with_name(p.stem + ".before_add.json")
    if p.exists() and not backup.exists():
        shutil.copy(p, backup)
    p.write_text(json.dumps(o, ensure_ascii=False, indent=1, default=str))


def llm(b):
    return LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=b)


def finish(entry):
    entry["rows"] = [r for r in entry["rows"] if not r["title"].lower().startswith("former")]
    entry["marketing_idx"] = R.marketing_idx(entry["rows"])
    entry["product_idx"] = R.product_idx(entry["rows"])
    return entry


# --- references ------------------------------------------------------------------------------------------
def ref_sprinklr(L):
    sub = json.loads(SEC.get(f"https://data.sec.gov/submissions/CIK{SPRINKLR_CIK:010d}.json").text())["filings"]["recent"]
    i = next(i for i, f in enumerate(sub["form"]) if f == "DEF 14A")
    acc, doc, date = sub["accessionNumber"][i], sub["primaryDocument"][i], sub["filingDate"][i]
    url = f"https://www.sec.gov/Archives/edgar/data/{SPRINKLR_CIK}/{acc.replace('-', '')}/{doc}"
    r = SEC.get(url)
    text = M.html_to_text(r.text(), limit=10_000_000)
    section = R.exec_officer_section(text, limit=16000)
    sha = RAW.put(r.body)
    ans = L.ask_json(JUDGE_MODEL, "sec_exec_officers/v1", R.SEC_PROMPT, section, max_tokens=4000)
    tn = M.norm(section)
    people = ans.get("people", [])
    kept = [p for p in people if M.quote_ok(p, tn)]
    rows = [{"name": p["name"], "title": p["title"], "responsibility": "", "quote": p["quote"]} for p in kept]
    return finish({"segment": "us_mid", "name": "Sprinklr", "kind": f"SEC DEF 14A filed {date}, executive officers (official filing)",
                   "tier": 1, "url": url, "sha256": sha, "rows": rows,
                   "notes": f"{len(people) - len(kept)} rows dropped (quote not in section)"})


def ref_typeform(L):
    url = "https://www.typeform.com/about-us/"
    r = KIT.get(url)
    sha = RAW.put(r.body)
    text = M.html_to_text(r.text())
    ans = L.ask_json(JUDGE_MODEL, "extract_people/v1", M.EXTRACT_PROMPT.format(company="Typeform"), text, max_tokens=4000)
    tn = M.norm(text)
    people = ans.get("people", [])
    kept = [p for p in people if M.quote_ok(p, tn)]
    rows = [{"name": p["name"], "title": p["title"], "responsibility": "", "quote": p["quote"]} for p in kept]
    return finish({"segment": "eu_mid", "name": "Typeform", "kind": "company's own page: leadership team", "tier": 2,
                   "url": url, "sha256": sha, "rows": rows, "notes": f"{len(people) - len(kept)} rows dropped (quote not on page)"})


def step_ref():
    refs = load("refs.json")
    L = llm(0.2)
    for slug, f in (("sprinklr", ref_sprinklr), ("typeform", ref_typeform)):
        refs[slug] = f(L)
        e = refs[slug]
        print(slug, len(e["rows"]), "rows ·", len(e["product_idx"]), "product:",
              [e["rows"][i]["name"] + " — " + e["rows"][i]["title"] for i in e["product_idx"]])
    save("refs.json", refs)
    print(f"model ${L.spent_usd:.3f}")


# --- plan --------------------------------------------------------------------------------------------------
def step_plan():
    plans = load("plans.json")
    L = llm(0.1)
    for seg in ("us_mid", "eu_mid"):
        info = S.SEGMENTS[seg]
        names = [c["name"] for c in S.COMPANIES.values() if c["segment"] == seg]
        q = f"Segment: {info['name']} ({info['country']}; {info['size']}). Example companies: {', '.join(names)}."
        plans[seg] = L.ask_json(PLANNER_MODEL, "plan_segment_product/v1", S.PLAN_PROMPT_PRODUCT, q)
        print(seg, [c["name"] for c in plans[seg]["categories"]])
    save("plans.json", plans)
    print(f"planner ${L.spent_usd:.3f}")


def company_queries(plan, c):
    by_cat = {}
    for cat in plan["categories"]:
        for t in cat["queries"][:2]:
            by_cat.setdefault(cat["name"], []).append(t.replace("{company}", c["name"]).replace("{company_local}", c["name_local"]))
    rr, i = [], 0
    total = sum(len(v) for v in by_cat.values())
    while len(rr) < min(QUERIES_PER_COMPANY, total):
        for cat, qs in by_cat.items():
            if i < len(qs) and len(rr) < QUERIES_PER_COMPANY:
                rr.append((cat, qs[i]))
        i += 1
    return rr


# --- search ------------------------------------------------------------------------------------------------
def step_search():
    plans, search = load("plans.json"), load("search.json")
    search["rows"] = [r for r in search["rows"] if r["company"] not in NEW]
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=1.2)
    for slug in NEW:
        c = S.COMPANIES[slug]
        for cat, q in company_queries(plans[c["segment"]], c):
            for routing, provs in (("pinned", PROVIDERS), ("auto", None)):
                try:
                    res = t.search(q, providers=provs, num_results=5)
                    runs = [{"provider": r.provider if routing == "pinned" else "auto", "status": r.status,
                             "latency_ms": r.latency_ms, "usd": r.usd, "hits": [h.__dict__ for h in r.hits]} for r in res.runs]
                except Exception as e:
                    runs = []
                    print("  search failed:", str(e)[:120])
                search["rows"].append({"company": slug, "category": cat, "query": q, "routing": routing, "runs": runs})
        print(slug, "spent", round(t.spent_usd, 3))
    search["spent_usd"] += t.spent_usd
    save("search.json", search)


# --- pick + read -------------------------------------------------------------------------------------------
def pick_for(search, slug):
    """Per company: domains its results returned (minus social/login sites and its own domains), ranked by how
    many providers returned them; the URL returned most often that names the company."""
    c = S.COMPANIES[slug]
    seen = defaultdict(lambda: {"providers": set(), "urls": defaultdict(lambda: [0, 99])})
    for row in search["rows"]:
        if row["company"] != slug:
            continue
        for run in row["runs"]:
            for h in run["hits"]:
                k = M.source_key(h["url"])
                if k in M.NOT_SOURCES or any(k.endswith(d) for d in c["own_domains"]) or h["url"].lower().endswith(".pdf"):
                    continue
                if c["url_token"] not in h["url"].lower():
                    continue
                x = seen[k]
                x["providers"].add(run["provider"])
                x["urls"][h["url"]][0] += 1
                x["urls"][h["url"]][1] = min(x["urls"][h["url"]][1], h["rank"])
    ranked = sorted(seen.items(), key=lambda kv: (-len(kv[1]["providers"]), -sum(v[0] for v in kv[1]["urls"].values()), kv[0]))
    return [(k, max(x["urls"].items(), key=lambda kv: (kv[1][0], -kv[1][1]))[0], sum(v[0] for v in x["urls"].values()))
            for k, x in ranked[:SOURCES_PER_COMPANY]]


def step_read():
    search, sources, reads = load("search.json"), load("sources.json"), load("reads.json")
    reads = [e for e in reads if e["company"] not in NEW]
    for s in sources:
        s["companies"] = [c for c in s["companies"] if c not in NEW]
        for c in NEW:
            s["urls"].pop(c, None)
    by_key = {s["key"]: s for s in sources}
    L = llm(1.0)
    for slug in NEW:
        c = S.COMPANIES[slug]
        for k, url, hits in pick_for(search, slug):
            s = by_key.get(k)
            if not s:
                s = {"key": k, "companies": [], "urls": {}, "hits": 0}
                sources.append(s)
                by_key[k] = s
            s["companies"] = sorted(set(s["companies"]) | {slug})
            s["urls"][slug] = url
            s["hits"] += hits
            e = {"source": k, "company": slug, "segment": c["segment"], "url": url}
            try:
                r = KIT.get(url)
                sha = RAW.put(r.body)
                ctype = r.headers.get("Content-Type", r.headers.get("content-type", "html"))
                if r.status != 200 or "html" not in ctype:
                    e.update(status=f"failed: HTTP {r.status}", sha256=sha)
                else:
                    text = M.html_to_text(r.text())
                    before = L.spent_usd
                    ans = L.ask_json(JUDGE_MODEL, "extract_people/v1", M.EXTRACT_PROMPT.format(company=c["name"]), text, max_tokens=8000)
                    tn = M.norm(text)
                    people = [p for p in ans.get("people", []) if M.quote_ok(p, tn)]
                    e.update(status="ok", sha256=sha, people=people,
                             dropped_unquoted=len(ans.get("people", [])) - len(people), extract_usd=L.spent_usd - before)
            except BlockedByRobots:
                e["status"] = "blocked_by_robots"
            except (FetchError, OSError) as ex:
                e["status"] = f"failed: {type(ex).__name__}"
            reads.append(e)
            print(slug, k, e["status"], len(e.get("people", [])))
    save("sources.json", sources)
    save("reads.json", reads)
    print(f"extraction ${L.spent_usd:.3f}")


# --- verify ------------------------------------------------------------------------------------------------
def step_verify():
    refs, reads, verified = load("refs.json"), load("reads.json"), load("verified.json")
    verified = [e for e in verified if e["company"] not in NEW]
    L = llm(0.5)
    for e in reads:
        if e["company"] not in NEW:
            continue
        ref = refs.get(e["company"])
        if e.get("status") != "ok" or not e.get("people") or not ref or not ref.get("rows"):
            verified.append({**e, "checks": [], "verify_usd": 0.0})
            continue
        rows = ref["rows"]
        a = "\n".join(f"{i}\t{p['name']}\t{p['title']}" for i, p in enumerate(e["people"]))
        b = "\n".join(f"{i}\t{r['name']}\t{r['title']}\t{r.get('responsibility', '')}" for i, r in enumerate(rows))
        before = L.spent_usd
        ans = L.ask_json(PLANNER_MODEL, "match_multi/v1",
                         M.MATCH_PROMPT.format(company=S.COMPANIES[e["company"]]["name"], ref_desc=ref["kind"]),
                         f"List A (index, name, title):\n{a}\n\nList B (index, name, rank/title, responsibility):\n{b}", max_tokens=8000)
        checks = M.verdicts(e["people"], rows, ans.get("matches", []), False)
        verified.append({**e, "checks": checks, "verify_usd": L.spent_usd - before})
        print(e["source"], e["company"], sum(c["employment"] == "correct" for c in checks), "/", len(checks))
    save("verified.json", verified)
    print(f"verify ${L.spent_usd:.3f}")


if __name__ == "__main__":
    steps = {"ref": step_ref, "plan": step_plan, "search": step_search, "read": step_read, "verify": step_verify}
    for name in (list(steps) if sys.argv[1] == "all" else [sys.argv[1]]):
        steps[name]()
