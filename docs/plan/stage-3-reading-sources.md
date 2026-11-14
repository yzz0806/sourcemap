# Stage 3 — Reading sources safely

## Goal
Run adapter code isolated from the worker, fetch politely, and read every known source.

## What gets built (`src/sourcemap/sandbox`, `src/sourcemap/adapters`)
- `sandbox.runner` / `sandbox.child`: one child process per call, clean environment with only the
  listed keys, timeout, CPU/memory limits, JSON over stdin/stdout (ADR 0008).
- `sandbox.kit`: polite fetch — robots.txt, per-host rate limit, back-off, raw bytes as served.
- Hand-written adapters: theorg, Open DART, LinkedIn via Apify (probe + lookup), OpenAlex, ORCID,
  company leadership pages, university directories (fetch only; extraction by judge, ADR 0006).
- First-party extraction: every extracted value must have a quote found in the visible text of
  the raw HTML, otherwise it is dropped and counted; the record links to its judge call.
- `sourcemap adapter <source> <unit>`: dev command to run one adapter on one unit.

## Order of work
Component doc → tests with fake HTTP and recorded fixtures (marked `slow` for real calls) → code →
`sandbox-and-adapters.md` updated → checks, log, commit, wait.

## How you check
1. theorg on Airtable: raw documents and a converted record. Open theorg.com/org/airtable and check
   3 people: name, title, manager.
2. OpenAlex on one department: confirm 2 names on openalex.org.
3. One LinkedIn lookup (~$0.004) for a person you know: candidates include them.
4. DART on Samsung Electronics (if the key is set): executives with titles. Without the key, the
   agent says DART is untested.
5. One company leadership page: every extracted person has a quote found in the raw HTML.
6. Safety demos: an adapter that sleeps forever is killed at the timeout ("timeout"); an adapter
   asking for an unlisted key is refused; a robots-disallowed page is blocked; the main process
   never imports adapter code (import-linter).
