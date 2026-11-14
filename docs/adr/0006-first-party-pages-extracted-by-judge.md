# 0006 — First-party pages (company leadership, university directories) are fetched raw and extracted by a judge call

Status: proposed (stage 0, under review)

## Context
Company leadership pages and university directories are the strongest references we have outside
Korea, but each site has its own layout. Hand-writing 16 + 17 parsers is too much for the demo;
agent-written adapters are out of scope.

## Decision
- The adapter only fetches: the page URL(s) are stored in the probe unit's identifiers, found once
  during setup (discovery may use Telem search restricted to the subject's own domain to find them).
- The raw HTML is stored unchanged as the raw fetch.
- The worker extracts people with one judge call over the visible text of that raw HTML, with a
  fixed prompt version, and stores the result as the record. The record links to the raw fetch, so
  every extracted value can be checked against the page.
- Because the extraction is *our* derivation, these sources are spot-checked like tier 1 (R9).

## Consequences
- One generic adapter covers all first-party pages.
- Extraction errors become source errors in the scores; the spot-checks measure them.
- Pages rendered only by JavaScript may return nothing; those units show `failed` coverage, not 0%.

## Alternatives rejected
- **Hand-written parser per site** — too many for the demo, and they break on every redesign.
- **Telem fetch for these pages** — returns a markdown rendering, not the raw response; not evidence.
- **Skip first-party sources** — would leave most non-Korean segments without any reference.
