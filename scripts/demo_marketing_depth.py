"""Marketing org chart below the CMO for US companies, whose official filings stop at the top officers.

  .venv/bin/python scripts/demo_marketing_depth.py search   # Telem: 8 marketing-department queries × you, brave, perplexity
  .venv/bin/python scripts/demo_marketing_depth.py read     # read the company's own leadership page + the best hits; extract marketing people
  .venv/bin/python scripts/demo_marketing_depth.py build    # merge people across pages, evidence level, branch → data/seg/marketing_depth.json
  .venv/bin/python scripts/demo_marketing_depth.py all

Evidence levels (shown on the chart):
  confirmed  — in the official filing (SEC 10-K / proxy executive officers: data/seg/refs.json)
  own_page   — named with a marketing title on the company's own website (tier 2)
  third_party— named only by other websites (tier 3+): shown with its sources, never counted as verified
Reporting lines are inferred from titles by a model and labelled as inferred. Search results only find pages (R2);
every person must quote text found on the saved page.
"""

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as M
from sourcemap.pipeline import demo_segments as S
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM, PLANNER_MODEL
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

D = Path("data/seg")
OUT = D / "marketing_depth.json"
WORK = D / "marketing_depth_work.json"
ENV = load_env(Path(".env"))
RAW = RawStore("data/raw")
KIT = Kit(min_interval_s=1.0, max_retries=2, timeout_s=40)
PROVIDERS = ["you", "brave", "perplexity"]  # best coverage in the provider benchmark
PAGES_PER_COMPANY = 20

COMPANIES = {
    "microsoft": {"own": ["microsoft.com", "microsoft.ai"], "leadership": ["https://news.microsoft.com/leadership/"]},
    "apple": {"own": ["apple.com"], "leadership": ["https://www.apple.com/leadership/"]},
    "nvidia": {"own": ["nvidia.com"], "leadership": ["https://nvidianews.nvidia.com/bios"]},
}
QUERIES = [
    "{company} chief marketing officer leadership team",
    "{company} corporate vice president marketing",
    "{company} vice president brand marketing",
    "{company} vice president product marketing",
    "{company} head of marketing appointed",
    "{company} marketing organization org chart",
    "{company} marketing executive joins",
    "site:{domain} vice president marketing",
]

# Second round: below the CMO, by product line and brand (step search2).
QUERIES_MORE = {
    "microsoft": ["Microsoft corporate vice president brand advertising research", "Microsoft Azure marketing corporate vice president",
                  "Microsoft 365 marketing corporate vice president", "Microsoft Windows Surface marketing vice president",
                  "Microsoft Xbox gaming marketing chief marketing officer", "Microsoft AI chief marketing officer"],
    "apple": ["Apple vice president iPhone product marketing", "Apple vice president Mac product marketing",
              "Apple vice president worldwide product marketing", "Apple vice president marketing communications",
              "Apple services marketing vice president", "Apple product marketing director keynote presenter"],
    "nvidia": ["Nvidia vice president GeForce marketing", "Nvidia vice president data center marketing",
               "Nvidia vice president enterprise marketing", "Nvidia chief marketing officer Alison Wagonfeld team",
               "Nvidia vice president developer marketing", "Nvidia head of brand marketing"],
}
MARKETING_TITLE = re.compile(r"market|brand|\bCMO\b|advertis|communications|growth", re.I)

EXTRACT = """From the page text, list the people the page presents as CURRENT marketing leaders at {company}:
anyone whose role is marketing, brand, advertising, product marketing, growth/consumer marketing, or marketing
communications, at director level or above (Director, Head, GM, VP, CVP, SVP, EVP, CMO). Copy each title exactly as
the page states it, and a short verbatim quote (under 200 characters) from the page text containing the person's name.
Skip people the page describes as former, retired or leaving. Do not add anyone not on the page.
Answer one JSON object only: {{"people": [{{"name": "...", "title": "...", "quote": "..."}}]}}"""

BRANCH = """You arrange {company}'s marketing leaders into an org chart from their titles alone.
Top: {cmo}. For each person below, give:
  "branch": a short name for the marketing area they lead or sit in (e.g. "Brand & advertising", "Product marketing — Cloud"),
            reusing the same branch name for people in the same area;
  "under_cmo": true if the title suggests they sit in the CMO's marketing organisation, false if it names another
            division or business (e.g. "CMO, Microsoft AI"), null if unclear;
  "rank": 1 for SVP/EVP/CVP/division CMO, 2 for VP/GM/Head, 3 for Senior Director/Director.
Do not invent people or titles. Answer one JSON object only:
{{"people": [{{"name": "...", "branch": "...", "under_cmo": true, "rank": 2}}]}}"""


def llm(b):
    return LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=b)


def work():
    return json.loads(WORK.read_text()) if WORK.exists() else {}


def save_work(w):
    WORK.write_text(json.dumps(w, ensure_ascii=False, indent=1))


def step_search():
    w = work()
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=0.6)
    for slug, cfg in COMPANIES.items():
        name = S.COMPANIES[slug]["name"]
        rows = []
        for tpl in QUERIES:
            q = tpl.format(company=name, domain=cfg["own"][0])
            try:
                res = t.search(q, providers=PROVIDERS, num_results=5)
                rows.append({"query": q, "hits": [{"provider": r.provider, **h.__dict__} for r in res.runs for h in r.hits]})
            except Exception as e:
                rows.append({"query": q, "error": str(e)[:200], "hits": []})
        w.setdefault(slug, {})["search"] = rows
        print(slug, sum(len(r["hits"]) for r in rows), "hits · spent", round(t.spent_usd, 3))
    w["search_usd"] = t.spent_usd
    save_work(w)


def step_search2():
    w = work()
    t = Telem(ENV["TELEM_API_KEY"], budget_usd=0.4)
    for slug, qs in QUERIES_MORE.items():
        rows = [r for r in w[slug]["search"] if r["query"] not in qs]
        for q in qs:
            try:
                res = t.search(q, providers=PROVIDERS, num_results=5)
                rows.append({"query": q, "hits": [{"provider": r.provider, **h.__dict__} for r in res.runs for h in r.hits]})
            except Exception as e:
                rows.append({"query": q, "error": str(e)[:200], "hits": []})
        w[slug]["search"] = rows
        print(slug, sum(len(r["hits"]) for r in rows), "hits · spent", round(t.spent_usd, 3))
    w["search_usd"] = w.get("search_usd", 0) + t.spent_usd
    save_work(w)


def is_own(url, cfg):
    h = M.host(url)
    return any(h == d or h.endswith("." + d) for d in cfg["own"])


def candidates(slug, cfg, rows):
    token = S.COMPANIES[slug]["url_token"]
    score = defaultdict(lambda: [set(), 0, ""])
    for r in rows:
        for h in r["hits"]:
            u = h["url"].split("#")[0]
            k = M.source_key(u)
            if k in M.NOT_SOURCES or u.lower().endswith(".pdf"):
                continue
            if token not in u.lower() and token not in (h.get("title") or "").lower():
                continue
            s = score[u]
            s[0].add(h["provider"])
            s[1] += 1
            s[2] = h.get("title") or ""
    ranked = sorted(score.items(), key=lambda kv: (-len(kv[1][0]), -kv[1][1], kv[0]))
    picked, per_key = [], defaultdict(int)
    for u, _ in ranked:
        k = M.source_key(u)
        if per_key[k] >= 3:  # at most 3 pages from one site
            continue
        per_key[k] += 1
        picked.append(u)
        if len(picked) >= PAGES_PER_COMPANY - len(cfg["leadership"]):
            break
    return cfg["leadership"] + [u for u in picked if u not in cfg["leadership"]]


def step_read():
    w = work()
    L = llm(0.6)
    for slug, cfg in COMPANIES.items():
        name = S.COMPANIES[slug]["name"]
        pages = []
        for url in candidates(slug, cfg, w[slug]["search"]):
            e = {"url": url, "source": M.source_key(url), "own": is_own(url, cfg)}
            try:
                r = KIT.get(url)
                e["sha256"] = RAW.put(r.body)
                ctype = r.headers.get("Content-Type", r.headers.get("content-type", "html"))
                if r.status != 200 or "html" not in ctype:
                    e["status"] = f"failed: HTTP {r.status}"
                else:
                    text = M.html_to_text(r.text())
                    ans = L.ask_json(JUDGE_MODEL, "extract_marketing/v1", EXTRACT.format(company=name), text, max_tokens=6000)
                    tn = M.norm(text)
                    people = [p for p in ans.get("people", []) if M.quote_ok(p, tn)]
                    e.update(status="ok", people=people, dropped_unquoted=len(ans.get("people", [])) - len(people))
            except BlockedByRobots:
                e["status"] = "blocked_by_robots"
            except (FetchError, OSError) as ex:
                e["status"] = f"failed: {type(ex).__name__}"
            pages.append(e)
            print(slug, e["source"], e["status"], len(e.get("people", [])))
        w[slug]["pages"] = pages
    w["read_usd"] = L.spent_usd
    save_work(w)
    print(f"extraction ${L.spent_usd:.3f}")


def norm_name(n):
    n = re.sub(r"[“\"'‘’].*?[”\"'‘’]|\(.*?\)", " ", n.lower())  # drop nicknames: Greg “Joz” Joswiak = Greg Joswiak
    return re.sub(r"[^a-z]", "", n)


def step_build():
    w, refs = work(), json.loads((D / "refs.json").read_text())
    L = llm(0.1)
    out = {}
    for slug, cfg in COMPANIES.items():
        name = S.COMPANIES[slug]["name"]
        ref = refs.get(slug, {})
        ref_mk = [ref["rows"][i] for i in ref.get("marketing_idx", [])]
        people = {}
        for pg in w[slug].get("pages", []):
            for p in pg.get("people", []):
                if not MARKETING_TITLE.search(p["title"]):  # extraction sometimes adds non-marketing leaders
                    continue
                k = norm_name(p["name"])
                if not k:
                    continue
                x = people.setdefault(k, {"name": p["name"], "titles": [], "sources": []})
                x["titles"].append(p["title"])
                x["sources"].append({"source": pg["source"], "url": pg["url"], "own": pg["own"], "title": p["title"],
                                     "quote": p["quote"][:200]})
        ref_names = {norm_name(r["name"]): r for r in ref_mk}
        for k, r in ref_names.items():
            people.setdefault(k, {"name": r["name"], "titles": [r["title"]], "sources": []})
        for k, x in people.items():
            x["level"] = "confirmed" if k in ref_names else "own_page" if any(s["own"] for s in x["sources"]) else "third_party"
            own_titles = [s["title"] for s in x["sources"] if s["own"]]
            x["title"] = ref_names[k]["title"] if k in ref_names else (own_titles or x["titles"])[0]
            x["n_sources"] = len({s["source"] for s in x["sources"]})
        cmo = next((x for x in people.values() if x["level"] == "confirmed"), None)
        if not cmo:  # no marketing officer in the filing: the most senior marketing title on the company's own site leads
            top = re.compile(r"chief marketing|worldwide marketing|global marketing|head of marketing|(senior|executive) vice president.*marketing", re.I)
            own = [x for x in people.values() if x["level"] == "own_page" and top.search(x["title"])]
            third = sorted([x for x in people.values() if re.search(r"chief marketing officer|\bCMO\b", x["title"], re.I)
                            and not re.search(r"former|consumer|, (microsoft )?ai\b", x["title"], re.I)], key=lambda x: -x["n_sources"])
            cmo = own[0] if own else (third[0] if third and third[0]["n_sources"] >= 2 else None)
        rest = [x for x in people.values() if x is not cmo]
        if rest:
            ans = L.ask_json(PLANNER_MODEL, "marketing_branches/v1",
                             BRANCH.format(company=name, cmo=f"{cmo['name']}, {cmo['title']}" if cmo else "the CMO (not identified)"),
                             "\n".join(f"{x['name']}\t{x['title']}" for x in rest), max_tokens=3000)
            by = {norm_name(a["name"]): a for a in ans.get("people", [])}
            for x in rest:
                a = by.get(norm_name(x["name"]), {})
                x["branch"], x["under_cmo"], x["rank"] = a.get("branch") or "Other marketing", a.get("under_cmo"), a.get("rank") or 3
        out[slug] = {"company": name, "reference": ref.get("kind"), "reference_url": ref.get("url"),
                     "cmo": cmo, "people": sorted(rest, key=lambda x: (x.get("rank", 3), x["name"])),
                     "pages": [{k: v for k, v in pg.items() if k != "people"} | {"n_people": len(pg.get("people", []))}
                               for pg in w[slug].get("pages", [])]}
        lv = defaultdict(int)
        for x in rest:
            lv[x["level"]] += 1
        print(name, "CMO:", cmo and cmo["name"], "·", dict(lv))
    out["_cost"] = {"search_usd": w.get("search_usd", 0), "read_usd": w.get("read_usd", 0), "build_usd": L.spent_usd}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    steps = {"search": step_search, "search2": step_search2, "read": step_read, "build": step_build}
    for n in (["search", "read", "build"] if sys.argv[1] == "all" else sys.argv[1:]):
        steps[n]()
