# 0002 — Multi-segment source benchmark: Samsung (KR), Nvidia (US), Airbus (EU)

## Question
"Which org-chart sources can you trust, by segment?" — fully automatic: plan → Telem search →
pick sources → read → verify against each segment's reference → accuracy, coverage, cost.

## Setup
- Code: `pipeline/demo_multi.py`, `scripts/demo_multi.py` (steps refs/plan/search/read/verify,
  each cached in `data/multi/`), page `scripts/demo_multi_page.py` → `data/multi/sourcemap_benchmark.html`.
- References: Samsung — DART 2025 annual report, 1,119 executives + 8 registered directors from the
  `exctvSttus` API (tier 1); Nvidia — nvidianews.nvidia.com/bios, 6 people (tier 2); Airbus —
  airbus.com executive & operational committees, 46 people (tier 2). Own pages found by a Telem
  search restricted to the company's domain.
- Planner and matcher `anthropic/claude-sonnet-5.5`; extractor `anthropic/claude-haiku-5.5`.
- Search: 12 queries per company × (exa, you, parallel, brave pinned + auto) = 72 calls.
- Sources picked automatically: domains found for ≥ 2 companies, minus own domains, social and
  login sites; top 9. Per company, the URL must name the company.

## Results
| Step | Cost |
|---|---|
| References (own-page extraction) | $0.004 |
| Planner × 3 | $0.03 |
| Search, 72 calls, 0 errors | $1.15 |
| Read + extract (quotes checked) | $0.03 |
| Verify (judge match) — incl. one redo after a reference bug | $0.65 |
| **Total for this experiment** | **≈ $1.90** (today overall ≈ $3.20) |

| Source | Employment (confirmed) | Title accuracy | Reads |
|---|---|---|---|
| theorg.com | 0.96 [0.89, 1.00] n=24 | 0.96 [0.89, 1.00] n=24 | 3/3 companies |
| querychart.io | 0.96 [0.88, 1.00] n=22 | 0.91 [0.79, 0.98] n=20, 1 wrong | 3/3 |
| wikipedia.org | 0.92 [0.76, 1.00] n=9 | 0.83 [0.64, 0.97] n=9, 1 wrong | 2/3 (Airbus not found) |
| marketscreener.com | 0.92 [0.78, 1.00] n=11 | 0.73 [0.49, 0.91] n=9, 2 wrong | Samsung only had people |
| nytimes.com, foxnews.com | not enough data (n=1) | | |
| investing.com, simplywall.st, theofficialboard.com | blocked automated reading (HTTP 403) | | |

## What we learned
- The planner reaches each country's official filings on its own (DART, SEC, Dutch/EU filings).
- Three of nine sources refuse automated reading; that is a property of the source and is shown,
  never counted as 0% coverage.
- Employment accuracy cannot go down with incomplete references (absent ≠ wrong); title accuracy
  is the number that separates sources (theorg 0.96 vs MarketScreener 0.73).
- My Samsung reference first missed the board directors (another DART table); theorg's Samsung page
  lists exactly those, so it showed 0/7. Fixed by adding the registered directors from the API.
- URL choice matters: the most-returned Wikipedia URL for Airbus was "Hercules"; URLs must name
  the company, else the source counts as not found.

## Follow-ups
- Official US/EU references (SEC 10-K executive officers; Airbus URD) instead of own pages.
- LinkedIn via Apify for non-executives; a person-level review sample to measure the judge.
- Tests for the demo modules; one `sourcemap demo` command.
