"""Runs the archive-measured checks for leadership-change signals v2 (pipeline/sig2_archive.py).

  .venv/bin/python scripts/sig2_archive.py locate   # find MarketScreener and theorg pages per company (Telem)
  .venv/bin/python scripts/sig2_archive.py run      # every event × source via Wayback → data/sig2/checks_archive.json
Re-runs reuse data/sig2/archive_cache/; results are written after every event so a crash loses nothing.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median

from sourcemap.cli import load_env
from sourcemap.pipeline import sig2_archive as A
from sourcemap.sandbox.kit import Kit
from sourcemap.services.websearch import Telem

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data/sig2"
CACHE = D / "archive_cache"
PAGES = CACHE / "pages_located.json"


def locate():
    env = load_env(ROOT / ".env")
    refs = json.loads((D / "refs.json").read_text())
    t = Telem(env["TELEM_API_KEY"], budget_usd=0.08)
    found = json.loads(PAGES.read_text()) if PAGES.exists() else {}
    for slug, c in refs["companies"].items():
        f = found.setdefault(slug, {})
        if "marketscreener.com" not in f:
            res = t.search(f"{c['name']} company governance executives site:marketscreener.com", providers=["parallel"], num_results=5)
            hits = [h.url for r in res.runs for h in r.hits if "marketscreener.com/quote/stock/" in h.url]
            if hits:
                m = re.match(r"(https://[^/]*marketscreener\.com/quote/stock/[^/]+/)", hits[0])
                f["marketscreener.com"] = (m.group(1) + "company-governance/") if m else hits[0]
            else:
                f["marketscreener.com"] = None
        if "theorg.com" not in f:
            res = t.search(f"{c['name']} org chart site:theorg.com", providers=["parallel"], num_results=5)
            hits = [h.url for r in res.runs for h in r.hits if re.match(r"https://(www\.)?theorg\.com/org/[^/?#]+", h.url)]
            f["theorg.com"] = ("https://theorg.com/org/" + re.match(r"https://(?:www\.)?theorg\.com/org/([^/?#]+)", hits[0]).group(1)) if hits else None
        f["finance.yahoo.com"] = f"https://finance.yahoo.com/quote/{c['ticker']}/profile"
        f["wikipedia.org"] = "https://en.wikipedia.org/wiki/" + c["wikipedia"].replace(" ", "_")
        print(slug, f)
    CACHE.mkdir(parents=True, exist_ok=True)
    PAGES.write_text(json.dumps(found, indent=1))
    print(f"located; Telem ${t.spent_usd:.3f}")


def run():
    refs = json.loads((D / "refs.json").read_text())
    pages = json.loads(PAGES.read_text())
    kit = Kit(min_interval_s=1.0, max_retries=4, timeout_s=60)
    arc = A.Archive(CACHE, kit)
    out_f = D / "checks_archive.json"
    done = {(c["event_id"], c["source"]): c for c in json.loads(out_f.read_text())} if out_f.exists() else {}
    events = refs["events"]
    for i, ev in enumerate(events, 1):
        for src in A.SOURCES:
            if (ev["id"], src) in done and done[(ev["id"], src)]["status"] != "error":
                continue
            done[(ev["id"], src)] = A.check(arc, src, pages.get(ev["company"], {}).get(src), ev)
        out_f.write_text(json.dumps(list(done.values()), indent=1))
        if i % 5 == 0 or i == len(events):
            st = Counter(c["status"] for c in done.values())
            print(f"{i}/{len(events)} events · requests {arc.requests} · {dict(st)}", flush=True)
    report(list(done.values()), arc.requests)


def report(checks, requests):
    print("\nper source:")
    for src in A.SOURCES:
        cs = [c for c in checks if c["source"] == src]
        st = Counter(c["status"] for c in cs)
        lates = [c["days_late"] for c in cs if c["status"] == "found"]
        widths = [c["bound_days"][1] - c["bound_days"][0] for c in cs if c.get("bound_days")]
        print(f"  {src:20} {dict(st)}  median days_late={median(lates) if lates else None}  median bound width={median(widths) if widths else None}")
    print("requests this run:", requests)


if __name__ == "__main__":
    {"locate": locate, "run": run, "report": lambda: report(json.loads((D / "checks_archive.json").read_text()), 0)}[sys.argv[1]]()
