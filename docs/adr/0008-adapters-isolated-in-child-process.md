# 0008 — Adapter code runs only in an isolated child process with a timeout, its own keys, and a polite fetch helper

Status: proposed (stage 0, under review)

## Context
Adapters talk to the outside world and may hang, loop, or misbehave. The brief fixes that adapter
code never runs in the main process. Even hand-written adapters (all of the demo's) should run the
same way, so agent-written ones can be added later without a new path.

## Decision
- `sandbox.runner` spawns `python -m sourcemap.sandbox.child` per call, with:
  - a **clean environment** containing only the keys listed in `adapter.keys_json`;
  - a **wall-clock timeout** (default 60 s per probe unit, 30 s per lookup), after which the process
    group is killed and the result is `timeout`;
  - CPU and memory limits (`resource.setrlimit`) in the child;
  - input and output as JSON over stdin/stdout; the child never opens the database.
- An adapter asking `kit.key()` for an unlisted key gets an error and the call is `refused`.
- All network access goes through `sandbox.kit` (robots.txt, per-host rate limit, exponential back-off
  on 429/5xx, generic user agent). Raw bytes are returned exactly as served.
- Import-linter: only `sandbox.child` may import `sourcemap.adapters`.

## Consequences
- A process start per call costs ~100 ms; at the demo's size that's negligible.
- An adapter could still bypass `kit` with its own HTTP import; for hand-written adapters, review and
  an import-linter rule (adapters may not import `httpx`/`requests`/`urllib`) prevent it.

## Alternatives rejected
- **Thread with a timeout in the worker** — a thread can't be killed, and it shares the worker's keys.
- **Docker per call** — strong isolation but heavy to set up and slow; not needed for hand-written code.
- **Run adapters in the worker and trust them** — the brief forbids it.
