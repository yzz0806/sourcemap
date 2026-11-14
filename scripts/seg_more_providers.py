"""Send the segment benchmark's pinned queries through the Telem providers it skipped.

The first run (scripts/demo_segments.py) pinned only exa, you, parallel and brave. This sends the
same 72 queries, one provider at a time, to the others and writes the merged result to
data/seg/search.json, after copying the original to data/seg/search.before_more_providers.json.
Same num_results (5). Estimated cost ~$1.50. Hits are never evidence (R2).

Run: .venv/bin/python scripts/seg_more_providers.py   then   .venv/bin/python scripts/build_web.py
"""

import json
import os
import shutil
from pathlib import Path

from sourcemap.services.websearch import Telem

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/seg/search.json"
BACKUP = ROOT / "data/seg/search.before_more_providers.json"
EXTRA = ["tavily", "perplexity", "linkup", "serpapi", "tinyfish"]


def key() -> str:
    if os.environ.get("TELEM_API_KEY"):
        return os.environ["TELEM_API_KEY"]
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("TELEM_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("TELEM_API_KEY not set")


def main() -> None:
    if not BACKUP.exists():
        shutil.copy(PATH, BACKUP)
    data = json.loads(PATH.read_text())
    t = Telem(key(), budget_usd=3.0)
    for row in data["rows"]:
        if row["routing"] != "pinned":
            continue
        have = {r["provider"] for r in row["runs"]}
        for p in EXTRA:
            if p in have:
                continue
            try:
                res = t.search(row["query"], providers=[p], num_results=5)
                runs = [{"provider": r.provider, "status": r.status, "latency_ms": r.latency_ms, "usd": r.usd,
                         "hits": [h.__dict__ for h in r.hits]} for r in res.runs] or \
                       [{"provider": p, "status": "no response", "latency_ms": None, "usd": 0.0, "hits": []}]
            except Exception as e:  # one failing call never stops the run
                runs = [{"provider": p, "status": str(e)[:200], "latency_ms": None, "usd": 0.0, "hits": []}]
            row["runs"].extend(runs)
        PATH.write_text(json.dumps(data, ensure_ascii=False))  # save as we go; a re-run skips done calls
    data["providers"] = sorted(set(data["providers"]) | set(EXTRA))
    data["spent_usd"] += t.spent_usd
    PATH.write_text(json.dumps(data, ensure_ascii=False))
    print("spent", round(t.spent_usd, 3))


if __name__ == "__main__":
    main()
