# 0001 — Samsung Electronics marketing org chart: find sources with Telem, measure them

## Question
"Where can I get Samsung Electronics' marketing department org chart, and which source should I
trust?" Two parts: which search provider (behind Telem) finds the sources, and how good the found
sources are, measured against the official reference.

## Setup
- Plan: `docs/plan/demo-samsung-marketing.md` (the one-day cut of stages 3–9).
- Planner: one OpenRouter call, `anthropic/claude-sonnet-5.5`, prompt `agents/prompts/plan_sources.md` (v1).
- Search: Telem `/v1/search`, providers brave, exa, tavily, perplexity, serpapi, you, parallel, linkup,
  tinyfish (each pinned), plus `auto_routing: "accuracy"`; `num_results` 5.
- Reference: DART, Samsung Electronics 2025 annual report (rcept_no 20260310002820), executive
  tables parsed from the raw report document (stored unchanged in the raw store).
- Source under test: theorg.com Samsung pages (raw page stored).
- Judge: `anthropic/claude-sonnet-5.5`, prompt `match_judge/v1` in `pipeline/demo_measure.py`.
- Scoring: stage 1 `measure.accuracy` (crowd-edited prior Beta(2,1), 90% interval, min 5 decisive).

## Results
| Run | Cost | Outcome |
|---|---|---|
| Planner | $0.02 | 7 publisher categories, 21 queries; DART category first; 3 categories skipped with reasons |
| Telem test query | ~$0.01 | Brave's #1 result for "삼성전자 임원 현황 사업보고서" was DART itself; Tavily's were blogs |
| Search, 21 queries × 9 providers + auto | ~$1.09 | 42 calls, 0 errors, 195 candidate sources |
| DART | $0 | 1,119 executives; 93 with marketing responsibilities in 10 units |
| theorg | $0 | 51 Samsung people on public pages; reports of a person are not in the public page data |
| Judge (match + titles) | $0.11 | 16 of 51 theorg people matched to DART executives |
| **Total** | **≈ $1.25** | |

**Provider leaderboard (known-answer trials, 9 per provider; before the blind review):**
Exa and You.com 7/9; Parallel and auto-routing 6/9; Brave 5/9; Tavily 4/9; Perplexity 3/9;
LinkUp and TinyFish 1/9; SerpAPI 0/9 (and ~12.8 s median latency). Intervals are wide at n = 9.

**theorg on Samsung, against DART:**
- Employment: 0.95, 90% [0.85, 1.00], n = 16 (16 correct).
- Title: 0.89, 90% [0.76, 0.98], n = 16 (15 correct, 1 wrong).
- 69% of theorg's people are unverifiable (engineers and managers DART doesn't list).
- Marketing coverage: **2 of 93** DART marketing executives appear on theorg.

## What we learned
- The planner matters: DART was found because the planner reasoned about Korean regulator filings,
  and the Korean-language query found it at rank 1 on Brave.
- Providers differ a lot on this task: Exa and You.com surfaced the known sources most often;
  SerpAPI never did. Parallel matched auto-routing at a fraction of the cost per good find.
- theorg is accurate where it overlaps the reference (top executives) but nearly empty for the
  marketing department (2/93). For this question, DART is the source; theorg is not.
- One real disagreement: theorg says Won-Jin Lee heads Visual Display; DART (2025-12-31) says he heads
  the Global Marketing Office. Either theorg is wrong or it reflects a 2026 move; the page shows it.
- DART's executive API (`exctvSttus`) returns only registered directors; the full executive list
  (미등기임원) is only in the report document.

## Follow-ups
- Blind review of 40 candidates, then re-run `scripts/demo_page.py` for precision.
- Parse DART's registered-director table too (the two co-CEOs are unverifiable today).
- theorg's deeper chart needs its API; LinkedIn via Apify would cover non-executives.
