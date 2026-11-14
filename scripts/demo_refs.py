"""Builds the segment references for the marketing org-chart benchmark → data/seg/refs.json.

  .venv/bin/python scripts/demo_refs.py            # all companies not yet in refs.json
  .venv/bin/python scripts/demo_refs.py --redo X   # rebuild one company

Korea: DART (tier 1). US: SEC 10-K executive officers (tier 1; EDGAR requests carry the
SEC_USER_AGENT contact from .env, never printed). Europe: the company's own leadership page (tier 2).
"""

import json
import sys
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import demo_multi as DM
from sourcemap.pipeline import demo_refs as R
from sourcemap.pipeline.demo_dart import fetch_reference
from sourcemap.sandbox.kit import BlockedByRobots, Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM
from sourcemap.services.websearch import Telem
from sourcemap.store.rawstore import RawStore

OUT = Path("data/seg/refs.json")
OUT.parent.mkdir(parents=True, exist_ok=True)
ENV = load_env(Path(".env"))
RAW = RawStore("data/raw")
KIT = Kit(min_interval_s=1.0, max_retries=2, timeout_s=60)
SEC = Kit(min_interval_s=0.3, max_retries=2, timeout_s=60, user_agent=ENV.get("SEC_USER_AGENT", ""))
LLM_ = LLM(ENV["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.3)
TELEM = Telem(ENV["TELEM_API_KEY"], budget_usd=0.05)

KR = {"samsung-electronics": ("Samsung Electronics", "00126380"), "sk-hynix": ("SK hynix", "00164779"),
      "naver": ("NAVER", "00266961")}
US = {"nvidia": ("Nvidia", 1045810), "apple": ("Apple", 320193), "microsoft": ("Microsoft", 789019)}
EU = {"airbus": ("Airbus", None, None),
      "sap": ("SAP", "sap.com", ["https://www.sap.com/about/company/leadership.html",
                                 "https://www.sap.com/about/company/leadership/executive-board.html"]),
      "siemens": ("Siemens", "siemens.com", ["https://www.siemens.com/global/en/company/about/management.html",
                                             "https://www.siemens.com/global/en/company/about/management/managing-board.html"])}


def finish(entry: dict) -> dict:
    # A reference lists who holds a role now: rows the source itself marks "Former …" are dropped.
    entry["rows"] = [r for r in entry["rows"] if not r["title"].lower().startswith("former")]
    entry["marketing_idx"] = R.marketing_idx(entry["rows"])
    return entry


def build_kr(slug):
    name, code = KR[slug]
    multi = Path("data/multi/refs.json")
    if slug == "samsung-electronics" and multi.exists():
        m = json.loads(multi.read_text())[slug]
        rows = [{"name": r["name"], "title": r["title"], "responsibility": r.get("responsibility", ""), "quote": ""}
                for r in m["rows"]]
        return finish({"segment": "kr_listed", "name": name, "kind": "DART 2025 annual report (official filing)",
                       "tier": 1, "url": m["url"], "sha256": m["sha256"], "rows": rows,
                       "notes": "executives from the report document + registered directors from exctvSttus (reused)"})
    ref = fetch_reference(KIT, ENV["OPENDART_API_KEY"], code, RAW)
    # Re-parse the stored document with the layout-tolerant parser (filers' tables differ).
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(RAW.get(ref["sha256"])))
    rows = R.dedupe([r for n in z.namelist() for r in R.parse_exec_rows_flex(z.read(n).decode("utf-8", errors="replace"))])
    ref["execs"] = rows
    # Registered directors are in another table; the exctvSttus API returns exactly them.
    r = KIT.get("https://opendart.fss.or.kr/api/exctvSttus.json",
                params={"crtfc_key": ENV["OPENDART_API_KEY"], "corp_code": code, "bsns_year": ref["year"],
                        "reprt_code": "11011"})
    RAW.put(r.body)
    have = {x["name"] for x in rows}
    added = 0
    for x in json.loads(r.text()).get("list", []):
        if x["nm"] not in have:
            rows.append({"name": x["nm"], "title": x["ofcps"], "responsibility": x.get("chrg_job") or "", "quote": ""})
            added += 1
    return finish({"segment": "kr_listed", "name": name, "kind": "DART 2025 annual report (official filing)",
                   "tier": 1, "url": ref["viewer_url"], "sha256": ref["sha256"], "rows": rows,
                   "notes": f"{len(ref['execs'])} executives from the report document + {added} registered directors"})


def build_us(slug):
    """Latest 10-K's executive-officer section; if the 10-K defers it (Apple), the latest DEF 14A."""
    name, cik = US[slug]
    sub = SEC.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json")
    recent = json.loads(sub.text())["filings"]["recent"]
    tried = []
    for form in ("10-K", "DEF 14A"):
        i = next((i for i, f in enumerate(recent["form"]) if f == form), None)
        if i is None:
            continue
        acc, doc, date = recent["accessionNumber"][i], recent["primaryDocument"][i], recent["filingDate"][i]
        url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{acc.replace('-', '')}/{doc}"
        r = SEC.get(url)
        if r.status != 200:
            tried.append(f"{form}: HTTP {r.status}")
            continue
        text = DM.html_to_text(r.text(), limit=10_000_000)
        section = R.exec_officer_section(text)
        if not section:
            tried.append(f"{form} {date}: no executive-officer section")
            continue
        sha = RAW.put(r.body)
        ans = LLM_.ask_json(JUDGE_MODEL, "sec_exec_officers/v1", R.SEC_PROMPT, section, max_tokens=4000)
        tn = DM.norm(section)
        people = ans.get("people", [])
        kept = [p for p in people if DM.quote_ok(p, tn)]
        if not kept:
            tried.append(f"{form} {date}: section found but no quoted officers")
            continue
        rows = [{"name": p["name"], "title": p["title"], "responsibility": "", "quote": p["quote"]} for p in kept]
        return finish({"segment": "us_listed", "name": name,
                       "kind": f"SEC {form} filed {date}, executive officers (official filing)", "tier": 1,
                       "url": url, "sha256": sha, "rows": rows,
                       "notes": "; ".join(tried + [f"{len(people) - len(kept)} rows dropped (quote not in section)"])})
    raise RuntimeError(f"SEC {slug}: " + "; ".join(tried))


def find_eu_page(name, domain, guesses):
    blocked = 0
    for u in guesses:
        try:
            r = KIT.get(u)
            if r.status == 200 and len(r.body) > 5000:
                return u, r
        except BlockedByRobots:
            blocked += 1
        except Exception:
            pass
    res = TELEM.search(f"{name} Executive Board members site:{domain}", providers=["exa", "brave"], num_results=5)
    for run in res.runs:
        for h in run.hits:
            if domain in h.url and not h.url.lower().endswith(".pdf"):
                try:
                    r = KIT.get(h.url)
                    if r.status == 200:
                        return h.url, r
                except BlockedByRobots:
                    blocked += 1
                except Exception:
                    continue
    if blocked:
        raise RuntimeError(f"{name}: {domain}'s robots.txt disallows automated reading of its leadership pages "
                           f"({blocked} candidate URLs blocked); no reference used")
    raise RuntimeError(f"{name}: no leadership page found on {domain}")


def build_eu(slug):
    name, domain, guesses = EU[slug]
    if slug == "airbus":
        m = json.loads(Path("data/multi/refs.json").read_text())[slug]
        rows = [{"name": r["name"], "title": r["title"], "responsibility": "", "quote": r.get("quote", "")}
                for r in m["rows"]]
        return finish({"segment": "eu_listed", "name": name, "kind": "company's own page: executive & operational committees",
                       "tier": 2, "url": m["url"], "sha256": m["sha256"], "rows": rows, "notes": "reused from data/multi"})
    url, r = find_eu_page(name, domain, guesses)
    sha = RAW.put(r.body)
    text = DM.html_to_text(r.text())
    ans = LLM_.ask_json(JUDGE_MODEL, "extract_people/v1", DM.EXTRACT_PROMPT.format(company=name), text, max_tokens=8000)
    tn = DM.norm(text)
    people = ans.get("people", [])
    kept = [p for p in people if DM.quote_ok(p, tn)]
    rows = [{"name": p["name"], "title": p["title"], "responsibility": "", "quote": p["quote"]} for p in kept]
    return finish({"segment": "eu_listed", "name": name, "kind": "company's own leadership page", "tier": 2,
                   "url": url, "sha256": sha, "rows": rows,
                   "notes": f"{len(people) - len(kept)} extracted rows dropped (quote not on page)"})


def main():
    refs = json.loads(OUT.read_text()) if OUT.exists() else {}
    redo = sys.argv[sys.argv.index("--redo") + 1] if "--redo" in sys.argv else None
    builders = {**{s: build_kr for s in KR}, **{s: build_us for s in US}, **{s: build_eu for s in EU}}
    for slug, build in builders.items():
        if slug in refs and slug != redo:
            continue
        try:
            refs[slug] = build(slug)
        except Exception as e:
            refs[slug] = {"segment": "?", "name": slug, "failed": f"{type(e).__name__}: {e}"[:300], "rows": [],
                          "marketing_idx": []}
        OUT.write_text(json.dumps(refs, ensure_ascii=False, indent=1))
    for slug, e in refs.items():
        status = e.get("failed") or e.get("notes", "")
        print(f"{slug:20} {e.get('segment', '?'):10} tier {e.get('tier', '-')}  rows {len(e['rows']):5}  "
              f"marketing {len(e['marketing_idx']):3}  {status[:90]}")
    print(f"cost: model ${LLM_.spent_usd:.3f}, search ${TELEM.spent_usd:.3f}")


if __name__ == "__main__":
    main()
