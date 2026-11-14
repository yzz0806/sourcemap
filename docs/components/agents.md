# Agents — `sourcemap.agents`

Agent sessions run through the Claude Agent SDK on the machine's Claude Code login (ADR 0007).
In the demo there is one agent: **discovery**. (Define, adapter-writing and gap agents of the full
product are out of scope.)

Each session: built-in tools turned **off explicitly** (an empty allow-list does not disable
them), only the task's own tools exposed, structured output required, cost and turns recorded in
`agent_session`, sessions per run capped by count.

| Module | Public functions (one line each) |
|---|---|
| `tools.py` | `web_search`, `web_fetch` — generic tools backed by `services.websearch`; agents never see provider names. |
| `discovery.py` | `plan_categories(data_type, segments) -> list[Category]` — one session; `search_category(category) -> list[SourceCard]` — one session per category, run in parallel; `merge_cards(cards) -> list[SourceCard]` — dedupe by domain. |
| `prompts/discovery_*.md` | Prompt texts. Tested as text: "lineage must be stated", "skip paid-contract or no-automation sources", "search only finds, never proves". |
| `fakes.py` | `FakeAgentRunner` — scripted structured outputs for tests. |

A `SourceCard`: name, URL, tier/subtype, lineage (per claim type if it differs), access, segments,
claim types it could verify, why, and `found_by` (search provider + query).
