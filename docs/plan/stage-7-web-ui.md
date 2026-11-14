# Stage 7 — Web UI

## Goal
The API and the web pages: catalog, map, cell drill-down, source page, run console with gates,
assembled data with export, history — plus a demo database for UI work.

## What gets built
- `sourcemap.api` (FastAPI) serving JSON and the built UI; read-only on the world (import-linter).
- `web/` (React + Vite): pages from `docs/components/api-and-web.md`. Map cells show coverage,
  interval, raw and weighted n, and the distinct states not enough data / unmeasured / not probed
  (incl. "no adapter") / failed / "k of N failed". Judge-calibration banner. Simulation banner.
- Time slider over map snapshots; history per cell with breakages and alerts.
- **Provider leaderboard** (centrepiece page), the blind gate-B review page, and the monitor page.

## Order of work
`api-and-web.md` refined → API tests on a demo database → API → UI → doc updated → checks, log,
commit, wait.

## How you check
1. Every page loads with no browser console errors.
2. A map cell's coverage and interval equal what stage 5a printed for the same run.
3. From a map cell to the raw evidence in 3 clicks or fewer.
4. Start a test run from the catalog; the console shows events live; approve a gate from the UI.
5. The time slider shows older snapshots.
6. Export the assembled data as CSV and open it.
7. Phone width (375 px): nothing overflows.
8. Stop the worker: the UI still shows the last map.
9. Open a simulation: the banner shows on every page and export is disabled.
10. Leaderboard numbers equal `sourcemap leaderboard` for the same run; click a provider to see the
    candidates it found; the pooled-recall limit is stated on the page.
11. Gate B review page shows no provider names.

## You need to provide
15 minutes in a browser for the checks (including phone width).

## Cost
$0 (works on the existing database; a test run started from the UI follows the stage 5a budget).
