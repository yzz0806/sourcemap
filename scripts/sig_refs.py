"""Builds the SEC 8-K Item 5.02 reference for leadership-change signals.

  .venv/bin/python scripts/sig_refs.py          → data/sig/refs.json  (Nvidia, Apple, Microsoft; 2024-11 → 2026-11)
  .venv/bin/python scripts/sig_refs.py --v2     → data/sig2/refs.json (ten US mega-caps; 2021-11-14 → 2026-11-14,
                                                  plus name/ticker/domain/newsroom/wikipedia and a de-duplicated
                                                  top-level "events" list)
SEC is free; judge extraction is cached (same prompt version and input never paid twice).
"""

import json
import sys
from pathlib import Path
from urllib.parse import quote

from sourcemap.cli import load_env
from sourcemap.pipeline import sig_refs as R
from sourcemap.pipeline.demo_multi import html_to_text
from sourcemap.sandbox.kit import Kit
from sourcemap.measure.names import normalise_name
from sourcemap.services.llm import JUDGE_MODEL, LLM
from sourcemap.store.rawstore import RawStore

OUT = Path("data/sig/refs.json")
OUT2 = Path("data/sig2/refs.json")


def main(v2: bool = False):
    env = load_env(Path(".env"))
    kit = Kit(user_agent=env["SEC_USER_AGENT"], min_interval_s=0.3, max_retries=3, timeout_s=60)
    raw = RawStore("data/raw")
    llm = LLM(env["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.3 if v2 else 0.4)
    window = R.WINDOW2 if v2 else R.WINDOW
    companies = {k: v["cik"] for k, v in R.COMPANIES2.items()} if v2 else R.COMPANIES
    out = {"window": list(window), "companies": {}}
    for slug, cik in companies.items():
        sub = json.loads(kit.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").text())
        recent = sub["filings"]["recent"]
        filings = R.filings_in_window(recent, window)
        oldest = min(recent["filingDate"]) if recent["filingDate"] else "9999"
        if oldest > window[0]:  # window not fully covered by "recent": read the older files too
            for f in sub["filings"].get("files", []):
                if f.get("filingTo", "9999") < window[0]:
                    continue  # this extra page ends before the window
                extra = json.loads(kit.get(f"https://data.sec.gov/submissions/{f['name']}").text())
                filings += R.filings_in_window(extra, window)
        uniq = {}
        for f in filings:
            uniq[f["accession"]] = f
        filings = list(uniq.values())
        comp = {"cik": cik, "filings": [], "events": []}
        if v2:
            comp.update({k: v for k, v in R.COMPANIES2[slug].items() if k != "cik"})
        n = 0
        for f in sorted(filings, key=lambda x: x["filing_date"]):
            url = R.doc_url(cik, f["accession"], f["primary"])
            rec = {"accession": f["accession"], "filing_date": f["filing_date"], "form": f["form"], "url": url, "items": f["items"]}
            try:
                r = kit.get(url)
                if r.status != 200:
                    raise RuntimeError(f"HTTP {r.status}")
                rec["sha256"] = raw.put(r.body)
                section = R.cut_502(html_to_text(r.text(), limit=400000))
                ans = llm.ask_json(JUDGE_MODEL, "sig_ref_extract/v1", R.EXTRACT_PROMPT, section, max_tokens=3000)
                evs = ans.get("events", [])
                kept = [e for e in evs if R.valid_event(e, section)]
                rec["events_extracted"], rec["events_kept"] = len(evs), len(kept)
                for e in kept:
                    n += 1
                    comp["events"].append({"id": f"{slug}-{n}", "company": slug, "person": e["person"], "change": e["change"],
                                           "role": e.get("role", ""), "kind": e.get("kind", "officer"),
                                           "effective_date": e.get("effective_date"), "filing_date": f["filing_date"],
                                           "accession": f["accession"], "url": url, "quote": e["quote"]})
            except Exception as ex:  # noqa: BLE001 — a failed filing is recorded, never invented
                rec["failed"] = str(ex)[:200]
            comp["filings"].append(rec)
        out["companies"][slug] = comp
        failed = sum(1 for f in comp["filings"] if f.get("failed"))
        print(slug, len(comp["filings"]), "filings,", len(comp["events"]), "events", f"({failed} failed)" if failed else "")
    if v2:
        out["events"] = R.dedupe_events([e for c in out["companies"].values() for e in c["events"]],
                                        lambda n: normalise_name(n).key)
        check_meta(out)
    dest = OUT2 if v2 else OUT
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"model spend ${llm.spent_usd:.4f} → {dest}")


def check_meta(out: dict) -> None:
    """Verify each newsroom loads (polite fetch) and each Wikipedia title exists; record the result."""
    kit = Kit(min_interval_s=0.5, max_retries=2, timeout_s=30)
    for slug, c in out["companies"].items():
        try:
            r = kit.get(c["newsroom"])
            c["newsroom_check"] = f"HTTP {r.status}"
        except Exception as ex:  # noqa: BLE001
            c["newsroom_check"] = type(ex).__name__
        try:  # the article page (robots.txt disallows /w/ and /api/ for bots)
            r = kit.get("https://en.wikipedia.org/wiki/" + quote(c["wikipedia"].replace(" ", "_"), safe="(),."))
            c["wikipedia_check"] = f"HTTP {r.status}" + (" (redirected: " + r.url.rsplit("/", 1)[-1] + ")" if r.status == 200 and not r.url.endswith(quote(c["wikipedia"].replace(" ", "_"), safe="(),.")) else "")
        except Exception as ex:  # noqa: BLE001
            c["wikipedia_check"] = type(ex).__name__


if __name__ == "__main__":
    main(v2="--v2" in sys.argv)
