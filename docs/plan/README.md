# Plan

The build in stages. Each stage file says the **goal**, **what gets built**, the **order of work**,
and **how you check it**. A stage is done only when every check passes and the user says go.

| Stage | File | Status |
|---|---|---|
| 0 | [Design on paper](stage-0-design.md) | done, awaiting approval |
| 1 | [Measuring rules, offline](stage-1-measuring-rules.md) | next |
| 2 | [Storage and starting content](stage-2-storage-and-seed.md) | — |
| 3 | [Discovery and the search-provider benchmark](stage-3-discovery-and-benchmark.md) — **centrepiece** | — |
| 4 | [Reading sources safely](stage-4-reading-sources.md) | — |
| 5 | [The daily pipeline, change monitor and drift](stage-5-daily-pipeline.md) | — |
| 6 | [Assembly](stage-6-assembly.md) | — |
| 7 | [Web UI](stage-7-web-ui.md) | — |
| 8 | [First live runs](stage-8-live-runs.md) | — |
| 9 | [Finish](stage-9-finish.md) | — |

Scope and the user's decisions: see `docs/agent/log.md` (both data types, 4 org-chart segments incl.
Korean listed, no human gold set, Telem for search, the search-provider benchmark as centrepiece
and the change monitor second). Rules: `docs/domain.md`.

## Order of work inside every stage

1. **Docs first** — update `docs/domain.md`, `docs/data-model.md`, `docs/containers.md` and the
   affected `docs/components/*.md` to describe what is about to be built; ADR for any real decision.
2. **Tests next** — rules as readable case tables (inputs → expected) before the code.
3. **Code** until the tests pass.
4. **Component docs** brought in line with the real modules and functions.
5. **Checks** — fast test suite, import-linter, the stage's own checks; commands and output shown.
6. **Session log** in `docs/agent/log.md`.
7. **Commit** with a clean `git status`, no `.env` or data files.
8. **Stop and wait** for the user.

## Checks for every stage

- [ ] **Tests pass** — "run the full fast test suite and show me the summary line". The count only goes up.
- [ ] **Layering holds** — "run the import-linter check": no broken contracts.
- [ ] **Docs match** — "which docs did you change in this stage?" New behaviour without a doc change is a red flag.
- [ ] **Decisions recorded** — "which decisions did you make, and where are the ADRs?"
- [ ] **Log written** — `docs/agent/log.md` has an entry for this stage.
- [ ] **Clean commit** — `git status` clean; `git log --stat -3` shows no `.env` or data files.
- [ ] **You can explain it** — in two sentences, what the stage added and how data flows through it.

**Red flags:** "tests skipped" without a reason; a rule from `docs/domain.md` §6 quietly weakened;
secrets in output; "done" without command output.

## Money

Total demo spend under about **$20**. The agent asks before any run over **$5**, any real-mode run,
anything near the Apify monthly cap, deleting data, or deploying.
