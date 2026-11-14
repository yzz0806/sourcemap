# Decisions

An accepted ADR is not rewritten; a new ADR supersedes it and the old one gets a pointer at the top.

| # | Decision |
|---|---|
| [0001](0001-records-as-json-with-versioned-schemas.md) | Records of any data type stored as JSON with versioned schemas; claims in fixed tables |
| [0002](0002-accuracy-standard.md) | Accuracy: weighted Beta posterior, tier priors, min 5 decisive checks, three display states |
| [0003](0003-verification-methods-and-ground-truth.md) | Verification by reference, lookup + judge, agreement; never web search; no human gold set |
| [0004](0004-entity-matching-before-verification.md) | Match mentions into entities before verifying; rules first, judge for borderline pairs |
| [0005](0005-lineage-per-source-and-per-claim-type.md) | Lineage per source with per-claim-type overrides |
| [0006](0006-first-party-pages-extracted-by-judge.md) | First-party pages fetched raw and extracted by a judge call |
| [0007](0007-agents-in-worker-via-claude-agent-sdk.md) | Agents in the worker via Claude Agent SDK, explicit tools, structured output |
| [0008](0008-adapters-isolated-in-child-process.md) | Adapters isolated in a child process with timeout, own keys, polite fetch |
| [0009](0009-model-providers.md) | Agent SDK for agents, OpenRouter for judge, second-family judge for calibration |
| [0010](0010-web-search-through-telem.md) | Web search through Telem behind one module, never for evidence |
| [0011](0011-sqlite-and-database-job-queue.md) | SQLite, database job queue, idempotent stages |
| [0012](0012-drift-health-and-verdict-expiry.md) | Source health, verdict expiry and re-checks, drift alerts |
