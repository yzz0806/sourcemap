"""Web search through Telem — the one module that calls it (ADR 0010).

`search()` sends one query to the named providers (pinned) or lets Telem pick (`auto`), and
returns every provider's hits with the provider, rank, title and snippet. Search results are for
*finding* sources only; they are never evidence (R2). Prices from docs.telem.ai (Prices table,
2026-11): most providers $0.005 a search; exa is billed as exa reports it (estimated here).
"""

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

BASE_URL = "https://router.telem.ai"
PRICE_USD = {"brave": 0.005, "ceramic": 0.00005, "exa": 0.005, "linkup": 0.005, "parallel": 0.001,
             "perplexity": 0.005, "seltz": 0.005, "serpapi": 0.006, "tavily": 0.005, "tinyfish": 0.0,
             "you": 0.005}


@dataclass(frozen=True)
class SearchHit:
    provider: str
    rank: int
    url: str
    title: str
    snippet: str


@dataclass
class ProviderRun:
    provider: str
    status: str               # "ok" or an error text
    latency_ms: int | None
    hits: list[SearchHit] = field(default_factory=list)
    usd: float = 0.0


@dataclass
class SearchResult:
    query: str
    routing: str                          # "pinned" or "auto"
    runs: list[ProviderRun]
    raw: dict

    @property
    def usd(self) -> float:
        return sum(r.usd for r in self.runs)


class OutOfBudget(Exception):
    pass


class Telem:
    def __init__(self, api_key: str, *, budget_usd: float, base_url: str = BASE_URL, timeout_s: float = 60):
        self._key = api_key
        self._base = base_url
        self._timeout = timeout_s
        self.budget_usd = budget_usd
        self.spent_usd = 0.0

    def search(self, query: str, *, providers: list[str] | None = None, num_results: int = 5) -> SearchResult:
        """One query to `providers` (pinned), or to Telem's auto-routing when providers is None."""
        est = sum(PRICE_USD.get(p, 0.005) for p in providers) if providers else 0.015
        if self.spent_usd + est > self.budget_usd:
            raise OutOfBudget(f"search would exceed budget ${self.budget_usd:.2f} (spent ${self.spent_usd:.3f})")
        search = {"num_results": num_results}
        if providers:
            search["providers"] = {"include": providers}
        else:
            search["auto_routing"] = "accuracy"
        body = json.dumps({"user_input": {"query": query}, "search": search}).encode()
        raw = self._post("/v1/search", body)
        runs = []
        for run in raw.get("preprocessor_runs", []):
            name = run.get("preprocessor_name", "?")
            out = run.get("output_payload") or {}
            err = run.get("error") or out.get("error")
            hits = [SearchHit(name, int(h.get("rank") or i + 1), h.get("url") or "", h.get("title") or "",
                              (h.get("summary") or "")[:400])
                    for i, h in enumerate(out.get("results") or []) if h.get("url")]
            runs.append(ProviderRun(name, "ok" if not err else str(err)[:200], out.get("latency_ms"), hits,
                                    PRICE_USD.get(name, 0.005)))
        result = SearchResult(query, "pinned" if providers else "auto", runs, raw)
        self.spent_usd += result.usd
        return result

    def _post(self, path: str, body: bytes, retries: int = 3) -> dict:
        req = urllib.request.Request(self._base + path, data=body, method="POST", headers={
            "Authorization": f"Bearer {self._key}", "Content-Type": "application/json"})
        for attempt in range(retries):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as r:
                    return json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt + 1 < retries:
                    time.sleep(float(e.headers.get("Retry-After", 2 ** attempt)))
                    continue
                raise RuntimeError(f"Telem {path}: HTTP {e.code} {e.read()[:300]!r}") from None
        raise RuntimeError(f"Telem {path}: gave up after {retries} attempts")
