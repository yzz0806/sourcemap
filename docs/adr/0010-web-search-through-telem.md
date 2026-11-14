# 0010 — Web search and page reading go through Telem, behind one module, never for evidence

Status: accepted (stage 0, approved by the user 2026-11-14). The user chose Telem over Tavily for this build.

## Context
Discovery needs web search and page reading. Telem (telem.ai) routes to many providers (Exa,
Tavily, Brave, Perplexity…) through `/v1/search` and `/v1/fetch`. Known traps: with no provider
list a query goes to every provider and `num_results` is per provider, so one query can cost 10×
the expected amount; Telem fetch returns a provider's markdown rendering, not the site's response.

## Decision
- One module, `services.websearch`, exposes `search()` and `fetch()`. Agents see only generic tools
  `web_search` / `web_fetch`.
- Every search pins 2–3 providers or uses `auto_routing: "accuracy"`; `num_results` ≤ 5 by default.
- Every call is charged to the run budget, from Telem's `usage` field when returned, otherwise from
  the provider's list price.
- 429 responses are retried after `Retry-After`.
- Each hit records which provider returned it; discovery stores this on the source card
  (`source.found_by_json`) so we can later see which provider finds the best sources.
- **Allowed:** discovery (planner and category agents); finding the leadership/people page of a
  probe unit by a search restricted to its own domain (ADR 0006).
- **Not allowed:** verifying claims (R2), and the fetches adapters make during probe. `fetch()`
  returns a `PageText` type that the evidence store refuses to save as a raw fetch.

## Consequences
- The provider can change without touching prompts or callers.
- Search cost is visible per run and per source card.

## Alternatives rejected
- **Tavily directly** (as the earlier implementation did) — one provider, no provenance comparison;
  the user chose Telem.
- **The Agent SDK's built-in web search** — outside our budget and provenance recording.
- **Telem with default routing** — the cost trap above.
