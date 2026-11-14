# 0007 — Agents run in the worker through the Claude Agent SDK, with explicit tools and structured output

Status: accepted (stage 0)

## Context
Discovery needs an agent that plans and searches. The brief fixes the Claude Agent SDK on the
machine's Claude Code login (no Anthropic API key). Known trap: an empty `allowed_tools` list does
not disable built-in tools (shell, file edit). A failed session may report $0 cost.

## Decision
- Agents run only in the worker process.
- Each session turns built-in tools off explicitly and exposes only the task's tools (`web_search`,
  `web_fetch`, backed by `services.websearch`). Tool names are generic; no provider names in prompts.
- Each session must return structured output matching a schema; a session without valid output is
  a failure, not a partial success.
- Sessions per run are capped by count (setting, default 8 for discovery) as well as by budget.
- Every session's cost, turns and output are stored in `agent_session`.
- Prompts live in files and are tested as text for the instructions that matter.

## Consequences
- An agent cannot touch the file system, the database or the shell.
- A runaway agent stops at the session cap even if it reports no cost.

## Alternatives rejected
- **Agents in the API process** — the API must not touch the internet or money.
- **Raw model API with a hand-made tool loop** — reimplements what the SDK does; the brief fixes the SDK.
- **Built-in web search tool of the SDK** — bypasses our budget and provenance recording.
