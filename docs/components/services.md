# Services — `sourcemap.services`

One module per outside service the **worker** calls directly. Each has a fake with the same
interface for tests. Every call that costs money takes a `Budget` and charges it before calling.
(Apify, DART, OpenAlex and ORCID are called from adapters inside the child process, see
`sandbox-and-adapters.md`.)

| Module | Public functions (one line each) |
|---|---|
| `websearch.py` | `search(query, *, providers, num_results, budget) -> list[SearchHit]` — Telem `/v1/search` with providers pinned or `auto_routing: "accuracy"`, each hit keeps its provider; `fetch(url, *, budget) -> PageText` — Telem `/v1/fetch`, typed as **not evidence**; 429 handled with `Retry-After`. (ADR 0010) |
| `judge.py` | `ask(questions, *, model, prompt_version, budget) -> list[Answer]` — batched OpenRouter calls, cached by input hash; question kinds `same_title`, `same_value`, `same_person`, `lookup_supports_claim`. (ADR 0009) |
| `budget.py` | `Budget(run_id, store)` with `reserve(service, est_usd)`, `settle(actual_usd)`; raises `OutOfBudget`. |
| `fakes.py` | `FakeWebSearch`, `FakeJudge` — deterministic, for tests. |
