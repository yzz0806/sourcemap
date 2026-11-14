# Stage 6 — Assembly

## Goal
One entry per real person across sources, each value from the source most accurate for that claim
type in that segment, every alternative kept with its origin; gate D and publish.

## What gets built
- Assemble stage using `measure.assemble.choose_value`; `assembled_value` rows with reasons.
- Gate D at the end of setup runs (sample of assembled entries); approval publishes and creates the
  daily maintenance schedule.
- CSV export of the assembled data (real database only).

## Order of work
Domain step 8 re-read → tests on winner choice, ties, unmeasured cells, alternatives → code →
`pipeline.md` updated → checks, log, commit, wait.

## How you check
1. A person in both theorg and LinkedIn at Airtable: **one** entry, both sources in provenance.
2. A field where sources disagree: the shown value comes from the source with better accuracy for
   that claim type and segment, the reason says so ("gong.io: title 0.92 vs theorg 0.71"), the other
   value is listed.
3. Two different people with similar names at one company stay separate.
4. "How many entities, how many in more than one source, how many pairs went to the judge?"
5. After gate D approval, a daily maintenance schedule exists.

## You need to provide
Gate D: look over a sample of about 10 assembled entries and approve or reject.

## Cost
About $0.10 (judge calls for any new borderline entity pairs; otherwise local).
