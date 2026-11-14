"""Builds data/sig/refs.json: SEC 8-K Item 5.02 events for Nvidia, Apple, Microsoft (2024-11-01 → 2026-11-14).

Run: .venv/bin/python scripts/sig_refs.py   (SEC is free; judge extraction < $0.40, cached)
"""

import json
from pathlib import Path

from sourcemap.cli import load_env
from sourcemap.pipeline import sig_refs as R
from sourcemap.pipeline.demo_multi import html_to_text
from sourcemap.sandbox.kit import Kit
from sourcemap.services.llm import JUDGE_MODEL, LLM
from sourcemap.store.rawstore import RawStore

OUT = Path("data/sig/refs.json")


def main():
    env = load_env(Path(".env"))
    kit = Kit(user_agent=env["SEC_USER_AGENT"], min_interval_s=0.3, max_retries=3, timeout_s=60)
    raw = RawStore("data/raw")
    llm = LLM(env["OPENROUTER_API_KEY"], Path("data/llm_cache"), budget_usd=0.4)
    out = {"window": list(R.WINDOW), "companies": {}}
    for slug, cik in R.COMPANIES.items():
        sub = json.loads(kit.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json").text())
        recent = sub["filings"]["recent"]
        filings = R.filings_in_window(recent)
        oldest = min(recent["filingDate"]) if recent["filingDate"] else "9999"
        if oldest > R.WINDOW[0]:  # window not fully covered by "recent": read the older files too
            for f in sub["filings"].get("files", []):
                extra = json.loads(kit.get(f"https://data.sec.gov/submissions/{f['name']}").text())
                filings += R.filings_in_window(extra)
        comp = {"cik": cik, "filings": [], "events": []}
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
                    comp["events"].append({"id": f"{slug}-{n}", "person": e["person"], "change": e["change"],
                                           "role": e.get("role", ""), "kind": e.get("kind", "officer"),
                                           "effective_date": e.get("effective_date"), "filing_date": f["filing_date"],
                                           "accession": f["accession"], "url": url, "quote": e["quote"]})
            except Exception as ex:  # noqa: BLE001 — a failed filing is recorded, never invented
                rec["failed"] = str(ex)[:200]
            comp["filings"].append(rec)
        out["companies"][slug] = comp
        print(slug, len(comp["filings"]), "filings,", len(comp["events"]), "events")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"model spend ${llm.spent_usd:.4f}")


if __name__ == "__main__":
    main()
