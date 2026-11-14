# Stage 4 — Reading sources safely, and the judge

## Goal
Run adapter code isolated from the worker, read every known source, and stand up the judge service
(first-party extraction needs it here; the pipeline uses it in 5a).

## What gets built
- `sandbox.runner` / `sandbox.child` around stage 2's `sandbox.kit`: one child process per call,
  clean environment with only the listed keys, timeout, CPU/memory limits, JSON over stdin/stdout
  (ADR 0008).
- **`services.judge`** (moved here from stage 5): OpenRouter, batched, cached by (model, prompt
  version, input hash); primary model chosen from the current OpenRouter list with its price and
  recorded in ADR 0009; the **easy-case suite** (identical titles, known translations such as
  대표이사 = CEO, clearly different people) must pass before the judge is used. Second-family
  calibration comes in 5b.
- Hand-written adapters: theorg, Open DART, LinkedIn via Apify (probe + lookup), OpenAlex, ORCID,
  company leadership pages, university directories (fetch only).
- First-party extraction by the judge (ADR 0006): every extracted value must have a quote found in
  the visible text of the raw HTML, otherwise it is dropped and counted; the record links to its
  judge call.
- `sourcemap adapter <source> <unit>`: run one adapter on one unit.

## Order of work
Component docs → tests with fake HTTP, fake judge and recorded fixtures (real calls marked
`slow`) → code → `sandbox-and-adapters.md`, `services.md` updated → a few real calls → checks,
log, commit, wait.

## How you check
1. theorg on Airtable: raw documents and a converted record. Open theorg.com/org/airtable and check
   3 people: name, title, manager.
2. OpenAlex on one department: confirm 2 names on openalex.org.
3. One LinkedIn lookup (~$0.004) for a person you know: candidates include them.
4. DART on Samsung Electronics: executives with titles (or "DART untested" without the key).
5. One company leadership page: every extracted person has a quote found in the raw HTML; the
   record links to its judge call.
6. Judge easy-case suite: all pass, with the model id and prompt version printed.
7. Safety demos: an adapter that sleeps forever is killed at the timeout ("timeout"); an adapter
   asking for an unlisted key is refused; a robots-disallowed page is blocked; the main process
   never imports adapter code (import-linter).

## You need to provide
- `APIFY_TOKEN` and `OPENROUTER_API_KEY` in `.env`; check the Apify monthly cap has room.
- The name of one real person (yours or a colleague's) for the LinkedIn lookup check.
- 10 minutes in a browser for checks 1, 2 and 5.

## Cost
About **$1**: a handful of Apify lookups and one company employee list for Airtable, judge calls
for a few pages and the easy-case suite (cents).
