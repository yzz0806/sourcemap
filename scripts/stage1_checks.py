"""Prints the stage 1 checks of docs/plan/stage-1-measuring-rules.md in readable form.

Run: .venv/bin/python scripts/stage1_checks.py   (no network, no keys)
"""

from datetime import datetime

from sourcemap.domain.model import Mention, Verification
from sourcemap.domain.vocab import Method, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for
from sourcemap.measure.match import match_mentions
from sourcemap.measure.transfer_gate import Features, apply_gate, representative

T = datetime(2026, 11, 14)


def vs(*kinds):
    return [Verification(i, Method.LOOKUP, Verdict(k), T) for i, k in enumerate(kinds)]


def show(label, est):
    iv = f"[{est.interval.lo:.3f}, {est.interval.hi:.3f}]" if est.interval else "none"
    m = f"{est.mean:.3f}" if est.mean is not None else "not shown"
    print(f"{label}\n   state={est.state.value} n={est.n_decisive} weighted_n={est.n_weighted} "
          f"mean={m} interval90={iv} stale={est.stale_share:.0%} unverifiable={est.unverifiable_share:.0%}")


def main():
    prior = prior_for(Tier.RESEARCHED)
    print("Hand check: crowd edited prior", prior, "+ 3 correct")
    e = estimate(vs("correct", "correct", "correct"), prior)
    print("   posterior", e.posterior, "posterior mean", round(e.posterior_mean, 3),
          "= (2+3)/(2+1+3) =", round(5 / 6, 3))
    show("   display:", e)
    show("2 correct + 1 stale + 1 unverifiable", estimate(vs("correct", "correct", "stale", "unverifiable"), prior))
    show("Only unverifiable", estimate(vs("unverifiable", "unverifiable"), prior))
    for n in (10, 200):
        c = int(n * 0.8)
        e = estimate(vs(*(["correct"] * c + ["wrong"] * (n - c))), prior)
        print(f"80% correct with {n} checks: mean {e.mean:.3f} "
              f"interval [{e.interval.lo:.3f}, {e.interval.hi:.3f}] width {e.interval.hi - e.interval.lo:.3f}")
    gate = representative(Features(1.0, 1.0, 10, "title"), Features(0.4, 4.0, 200, "title"))
    print("Gate (Samsung: 27 execs vs the rest):", "passed" if gate.passed else "FAILED", gate.reasons)
    show("   cell with overlap verdicts dropped",
         estimate(apply_gate(vs(*["correct"] * 7), gate) + vs("wrong", "wrong"), prior))
    print("Name pairs:")
    for a, b in [("Dr. Jane Smith", "Jane Smith"), ("John Smith", "Jane Smith"), ("J. Smith", "Jane Smith"),
                 ("Park, Hyung-Kwan", "HYUNG KWAN PARK"), ("박형관", "Hyung-Kwan Park")]:
        r = match_mentions([Mention(1, 1, 7, a), Mention(2, 2, 7, b)], [], [], next_entity_id=100)
        d = "judge" if r.judge_questions else ("same" if r.assignments[1] == r.assignments[2] else "different")
        print(f"   {a!r:22} / {b!r:20} -> {d}")


if __name__ == "__main__":
    main()
