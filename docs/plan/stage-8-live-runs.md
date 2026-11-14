# Stage 8 — First live runs (experiment 0001)

## Goal
Run the whole system for real on a fresh database in test mode, fix what breaks, and write it up.

## What gets run
- A benchmark run per data type on the fresh database (or the stage 3 run, re-scored with the
  measured quality of the sources each provider found).
- A setup run for org chart through gates B and D.
- Org-chart maintenance twice (the second on a later day).
- Academic-identity maintenance once.
- The departure and broken-source scenarios in simulation copies.
Every run within budget; the agent asks before anything over $5.

## Order of work
Fresh database → runs → bugs each fixed with a failing-first test → `docs/experiments/0001-demo.md`
→ checks, log, commit, wait.

## How you check
1. `docs/experiments/0001-demo.md` has: what was run, a cost table per run, the final map numbers,
   judge calibration, matching quality, the provider leaderboard, any real change-monitor case
   (or "none caught"), and what surprised us.
2. Every bug it lists has a fix commit with a test.
3. "What we learned" contains only things the runs showed.
4. Total spend roughly matches the Apify, OpenRouter and Telem dashboards.
