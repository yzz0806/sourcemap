"""Search for the Samsung Electronics marketing-department org chart, Tavily only (via Telem).

Run from the project root:  .venv/bin/python experiment/tavily-samsung-marketing-orgchart/run.py
Writes results.json next to this file. Search hits are leads, never evidence (R2).
"""

import json
import os
from pathlib import Path

from sourcemap.services.websearch import Telem

HERE = Path(__file__).parent
PROVIDER = "tavily"
NUM_RESULTS = 10
QUERIES = [
    "Samsung Electronics marketing department org chart",
    "Samsung Electronics marketing leadership team CMO",
    "Samsung Electronics Global Marketing Office head",
    "삼성전자 마케팅 조직도 임원",
    "삼성전자 글로벌마케팅실 전략마케팅실 임원",
]


def api_key() -> str:
    if os.environ.get("TELEM_API_KEY"):
        return os.environ["TELEM_API_KEY"]
    for line in Path(".env").read_text().splitlines():
        if line.startswith("TELEM_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"')
    raise SystemExit("TELEM_API_KEY not set")


def main() -> None:
    telem = Telem(api_key(), budget_usd=0.25)
    out = []
    for q in QUERIES:
        res = telem.search(q, providers=[PROVIDER], num_results=NUM_RESULTS)
        for run in res.runs:
            out.append({"query": q, "provider": run.provider, "status": run.status,
                        "latency_ms": run.latency_ms, "usd": run.usd,
                        "hits": [h.__dict__ for h in run.hits]})
            print(f"\n### {q}  [{run.provider} {run.status} {run.latency_ms}ms]")
            for h in run.hits:
                print(f"{h.rank:>2}. {h.url}\n    {h.title[:110]}\n    {h.snippet[:220]!r}")
    (HERE / "results.json").write_text(json.dumps(
        {"provider": PROVIDER, "num_results": NUM_RESULTS, "spent_usd": telem.spent_usd, "results": out},
        ensure_ascii=False, indent=1))
    print(f"\nspent ${telem.spent_usd:.3f}")


if __name__ == "__main__":
    main()
