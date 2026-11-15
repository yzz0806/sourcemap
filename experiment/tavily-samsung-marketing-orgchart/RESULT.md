# Samsung Electronics marketing org chart — Tavily only

Run 2026-11-14 · Telem with provider pinned to `tavily` · 5 queries × 10 results · $0.025.
Raw hits: `results.json`. Re-run: `.venv/bin/python experiment/tavily-samsung-marketing-orgchart/run.py`.
Everything below comes from search snippets, not opened pages: leads to check, not evidence (R2).

## Answer
Samsung does not publish an org chart for marketing. A partial chart has to be assembled from:

| Source | What it gives | Found by query |
|---|---|---|
| theorg.com/org/samsung | "Marketing and Product Management" team, 401 people (crowd-edited) | org chart |
| news.samsung.com/kr — 2026 정기 임원 인사 (2025-11-25) and 2025 list | Official unit + title per promoted executive | Korean queries |
| samsung-dxrecruit.com/dept/detail/C0010 | Samsung's own description of the Global Marketing Office (글로벌마케팅실) and its teams | Korean, office |
| news.samsung.com/global — "Announces New Leadership" | Head of Global Marketing Office appointment | office head |
| mk.co.kr 12034800 (KR + EN), thebell.co.kr (2026-05-07) | **2026-05 reorganisation** of the office (below) | office head |
| news.samsung.com/us/about/executive-bios, samsung.com/us leadership page | US / North America leadership | CMO |
| theofficialboard.com, bizkonnect.ai | Paid/aggregated charts (729 leaders; SEA marketing) | org chart |
| Naver blogs (dealsite, for_my_blog) | Executive lists with units, e.g. strategic-marketing heads | Korean |

## What the snippets say about the structure (unverified)
- **Global Marketing Office (DX, 글로벌마케팅실)**: Lee Young-hee (President) → Wonjin Lee (President, ex-Google).
  **May 2026**: Wonjin Lee moved to head Visual Display (VD); the office stopped being a president-level
  organisation and now reports directly to the DX Division (mk.co.kr). thebell: VP **Choi Seung-eun**
  (최승은, external hire) appointed to its successor organisation.
  - Brand Marketing Group head: **Choi Bo-ram** (최보람), promoted to 상무 in the 2026 list.
- **MX Strategic Marketing Office (전략마케팅실)**: 최방섭 부사장 listed as head (older blog list).
- **VD Strategic Marketing Team (전략마케팅팀)**: 이헌 부사장 (dealsite).
- **Samsung Electronics America**: CMO Allison Stransky — leaving for Boston Beer (Instagram, LinkedIn now
  shows Boston Beer); MX CMO Olga Suvorova (bizkonnect); Cathy Oh (TV & mobile services/advertising).
  Yoonie Joung, President & CEO North America, was previously head of the Global Strategic Marketing Office.
- **DS (semiconductor)**: strategic-marketing heads change per business unit; 한진만 (now President) was once
  head of DS strategic marketing.

## Notes on Tavily
- All 5 calls succeeded, ~0.9–1.2 s each.
- Korean queries returned official Samsung newsroom pages and the recruit site; these had the most
  useful structure.
- Noise: tavily.com's own company card in 3 of 5 queries, plus generic structure essays (Scribd,
  Slideshare, Edraw, ResearchGate) and one K-pop fan post.
- Did not return the theorg team page for marketing that Exa found earlier (it returned the company page).
