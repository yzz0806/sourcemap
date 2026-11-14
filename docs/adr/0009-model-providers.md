# 0009 — Model providers: Claude Agent SDK for agents, OpenRouter for judge calls

Status: proposed (stage 0, under review)

## Context
Two kinds of model work: multi-step agent sessions (discovery) and many small, cheap comparisons
(same title? same person? does this profile support this claim? extract people from this page).
The brief fixes the Agent SDK on the local login for agents and OpenRouter for judge calls. The
judge's error must be estimated without humans (ADR 0003), which needs a second, independent model.

## Decision
- **Agents:** Claude Agent SDK, local Claude Code login, default model set in settings.
- **Judge:** single OpenRouter chat calls with JSON output, batched (several questions per call
  where the prompt allows) and cached in `judge_call` by (model, prompt version, input hash).
  - Primary judge: a small, cheap model (exact OpenRouter model id chosen and recorded at stage 4,
    where first-party extraction first needs the judge, from the current OpenRouter list, with its price).
  - Second judge: a model from a **different family**, used on a sample each run for calibration.
- Every judge prompt has a version. Changing the model or prompt re-runs the easy-case suite and
  starts a new calibration series; cached answers from the old version are not reused.
- Judge answers always include a short reason and, for lookups, the quoted evidence span.

## Consequences
- Judge cost is a few cents per run in test mode; cached repeats are free.
- Calibration numbers are tied to a model + prompt version and shown with them.

## Alternatives rejected
- **Agent sessions for comparisons** — 100× the cost and slower, for single-step questions.
- **One provider for everything** — a second-family judge is what makes calibration meaningful.
- **String similarity instead of a judge for titles** — fails on "VP Sales" vs "Vice President of
  Sales" vs "영업 부사장".
