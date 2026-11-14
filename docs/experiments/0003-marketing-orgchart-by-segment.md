# 0003 — Marketing org charts by segment: one reference type per segment, 3 companies each

## Question
Which sources can you trust for a company's marketing org chart, **per segment**?

## Setup
- Segments and references (`pipeline/demo_segments.py`, `pipeline/demo_refs.py`):
  Korean listed — DART annual reports (tier 1): Samsung Electronics 1,127 people / 93 marketing,
  SK hynix 192 / 0, NAVER 154 / 5. US listed — SEC (tier 1): Nvidia 10-K 5 / 0, Apple DEF 14A 5 / 0,
  Microsoft 10-K 6 / 1. European listed — own pages (tier 2): Airbus 46 / 0, Siemens 21 / 0,
  SAP none (sap.com robots.txt disallows all bots). SEC requests carry the contact User-Agent from `.env`.
- One planner call per segment (query templates); 8 queries per company × (exa, you, parallel, brave
  + auto) = 144 Telem calls. Sources = domains found for ≥ 3 companies (top 10, sec.gov excluded).
- Steps: `scripts/demo_segments.py plan|search|read|verify`, refs `scripts/demo_refs.py`,
  page `scripts/demo_segments_page.py` → `data/seg/sourcemap_segments.html`.

## Results
Cost: planner $0.04, references $0.03, search $2.23, extraction ≈ $0.05, verification $0.55 →
**≈ $2.90**. (One search run of 144 calls failed with Cloudflare error 1010 and was not charged.)

Title accuracy (90% interval) by segment:
| Source | Korean listed | US listed | European listed |
|---|---|---|---|
| theorg.com | 0.90, n=17, 1 wrong | **0.62, n=5, 2 wrong** | 0.94, n=13 |
| wikipedia.org | 0.92, n=9 | unmeasured | not enough data (n=4) |
| digitaldefynd.com | 0.83, n=16, 2 wrong | 0.77, n=11, 2 wrong | unmeasured |
| derrick-app.com | unmeasured | 0.93, n=13 | unmeasured |
| rocketreach.co | not enough data | unmeasured (lists people no reference has) | unmeasured |
| theofficialboard.com, organimi.com | blocked | blocked | blocked |

Marketing coverage: no source names more than one of a segment's reference marketing executives.

## What we learned
- The same source differs by segment (theorg 0.90 / 0.62 / 0.94): scoring per segment matters (R1).
- Official data goes deep only in Korea; SEC and European pages stop at ~5–20 top people, so
  marketing claims outside Korea are mostly unverifiable — not wrong.
- No public source we found covers marketing org charts; DART is the only one, and only in Korea.
- DART table layouts differ by company (extra columns, Korean date formats); Apple's latest 10-K has
  no executive-officer section (fell back to the proxy statement).
- Telem's Cloudflare started refusing Python's default urllib User-Agent mid-day (error 1010); the
  client now sends its own User-Agent.

## Follow-ups
- Fix the shared DART parser with the layout-tolerant one (`demo_refs.parse_exec_rows_flex`).
- More companies per segment for narrower intervals; LinkedIn for non-executives.
- Next data type: technographics (discussed with the user; designed in the session, not built).
