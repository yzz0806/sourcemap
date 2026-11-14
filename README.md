# sourcemap

sourcemap tells you, with evidence, which public source to trust for which kind of entity and
which kind of fact, and keeps that answer current.

For a kind of data (org charts, academic identities), it finds the sources that publish it, reads
them, checks their statements against other sources, and draws a **map**: segments × sources, each
cell with coverage and an honest accuracy interval. Every number opens up to the checks behind
it, and every check to a saved copy of what the source returned.

> Status: **stage 0, design only.** There is no code yet. See `docs/agent/log.md`.

## Read in this order

1. `docs/domain.md` — the problem, the vocabulary, the pipeline and the accuracy rules. The
   source of truth for behaviour.
2. `docs/containers.md` — the processes, stores and outside services.
3. `docs/data-model.md` — the database.
4. `docs/components/` — one doc per part of the system.
5. `docs/adr/` — the decisions and why.
6. `docs/agent/log.md` — what happened in each session and what is open.

## Demo scope

- Two data types: **org chart** (16 companies in 4 segments) and **academic identity**
  (17 departments in 4 segments).
- Sources: theorg.com, Open DART, LinkedIn via Apify, OpenAlex, ORCID, company leadership pages,
  university directories.
- No human-labelled gold set: ground truth comes from reference sources and cross-lineage
  lookups (ADR 0003).

## Running it

_To be written in later stages._ Planned commands:

```
sourcemap seed                     # load starting content into a fresh database
sourcemap worker                   # the worker process (all internet, model and paid work)
sourcemap api                      # the API + web UI
sourcemap run maintenance org_chart --mode test
sourcemap map org_chart            # print the map in the terminal
```

Keys go in `.env` (never committed): `TELEM_API_KEY`, `OPENROUTER_API_KEY`, `APIFY_TOKEN`,
`OPENDART_API_KEY` (optional), `OPENALEX_EMAIL` (optional, polite pool). Agents use the local
Claude Code login.
