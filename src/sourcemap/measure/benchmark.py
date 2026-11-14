"""Search-provider benchmark arithmetic: URL normalising, known-answer scoring, candidates, metrics.

Implements ADR 0015 and docs/domain.md §10. Case tables: tests/cases/benchmark_cases.py.
Pure: URL parsing is done by hand (no urllib, per the "pure core" import-linter contract).
"""

import random
import re
from collections.abc import Iterable
from dataclasses import dataclass
from statistics import median

from sourcemap.measure.accuracy import beta_interval

MIN_TRIALS = 5  # same threshold as accuracy cells (ADR 0002)

SECOND_LEVEL_SUFFIXES = frozenset(
    {"co.uk", "ac.uk", "org.uk", "gov.uk", "co.kr", "ac.kr", "or.kr", "go.kr", "re.kr",
     "com.au", "edu.au", "co.jp", "ac.jp", "com.cn", "edu.cn", "com.br"}
)

_SCHEME = re.compile(r"^[a-z][a-z0-9+.\-]*://", re.IGNORECASE)


def _split(u: str) -> tuple[str, str]:
    """Return (host, path) with scheme, query, fragment, port and www. removed."""
    u = _SCHEME.sub("", u.strip())
    u = u.split("#", 1)[0].split("?", 1)[0]
    host, _, path = u.partition("/")
    host = host.lower().split("@")[-1].split(":", 1)[0]
    if host.startswith("www."):
        host = host[4:]
    return host, path.rstrip("/")


def normalise_url(u: str) -> str:
    """'https://www.TheOrg.com/org/gong/?x=1#y' → 'theorg.com/org/gong'. Host lowercased, path kept."""
    host, path = _split(u)
    return f"{host}/{path}" if path else host


def registrable_domain(host: str) -> str:
    """Last two labels, or last three under a known second-level suffix (co.uk, ac.kr, …)."""
    labels = [label for label in host.lower().split(".") if label]
    if len(labels) >= 3 and ".".join(labels[-2:]) in SECOND_LEVEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def candidate_key(u: str) -> str:
    """Registrable domain + '/' + first path segment: the level at which hits collapse to a source."""
    host, path = _split(u)
    first = path.split("/", 1)[0] if path else ""
    return f"{registrable_domain(host)}/{first}"


def score_known_answer(expected_url: str, hits: list[str]) -> tuple[bool, int | None]:
    """(hit, 1-based rank) of the first hit equal to the expected URL or a page below it."""
    expected = normalise_url(expected_url)
    for rank, h in enumerate(hits, start=1):
        n = normalise_url(h)
        if n == expected or n.startswith(expected + "/"):
            return True, rank
    return False, None


@dataclass(frozen=True, slots=True)
class Hit:
    """One search result: which provider returned it, for which query, at which rank."""

    provider: str
    query_id: int
    rank: int
    url: str
    segment: str | None = None


@dataclass(frozen=True, slots=True)
class Candidate:
    """Hits collapsed by candidate_key. Remembers every provider, rank and query that found it."""

    key: str
    example_url: str
    providers: frozenset[str]
    ranks: tuple[tuple[str, int], ...]
    query_ids: frozenset[int]
    segments: frozenset[str]


def to_candidates(hits: Iterable[Hit]) -> list[Candidate]:
    """Collapse hits into candidates, sorted by key."""
    groups: dict[str, list[Hit]] = {}
    for h in hits:
        groups.setdefault(candidate_key(h.url), []).append(h)
    out = []
    for key in sorted(groups):
        hs = groups[key]
        out.append(Candidate(
            key=key,
            example_url=min(hs, key=lambda h: (h.rank, h.url)).url,
            providers=frozenset(h.provider for h in hs),
            ranks=tuple(sorted((h.provider, h.rank) for h in hs)),
            query_ids=frozenset(h.query_id for h in hs),
            segments=frozenset(h.segment for h in hs if h.segment),
        ))
    return out


def review_sample(candidates: Iterable[Candidate], cap: int = 80, seed: int = 0) -> list[Candidate]:
    """At most `cap` candidates for blind review, seeded; random order (all of them if ≤ cap)."""
    pool = sorted(candidates, key=lambda c: c.key)
    rng = random.Random(seed)
    if len(pool) <= cap:
        rng.shuffle(pool)
        return pool
    return rng.sample(pool, cap)


@dataclass(frozen=True, slots=True)
class KnownTrial:
    """One known-answer trial: a provider searched for a seeded identifier."""

    provider: str
    hit: bool
    rank: int | None
    segment: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderCall:
    """One search call's outcome, for failure state, cost and latency."""

    provider: str
    ok: bool
    usd: float = 0.0
    latency_ms: float | None = None
    segment: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderMetric:
    """One leaderboard number. Proportions carry num/den, a 90% interval and a state; `mean` is
    shown only when measured. Counts and money have no interval."""

    provider: str
    segment: str | None
    metric: str
    num: float | None
    den: float | None
    mean: float | None
    lo90: float | None
    hi90: float | None
    state: str  # "measured" | "not_enough_data" | "failed"


def _proportion(provider, segment, metric, num, den, failed) -> ProviderMetric:
    if failed:
        return ProviderMetric(provider, segment, metric, num, den, None, None, None, "failed")
    if den == 0:
        return ProviderMetric(provider, segment, metric, num, den, None, None, None, "not_enough_data")
    a, b = 1 + num, 1 + den - num
    iv = beta_interval(a, b)
    if den < MIN_TRIALS:
        return ProviderMetric(provider, segment, metric, num, den, None, iv.lo, iv.hi, "not_enough_data")
    return ProviderMetric(provider, segment, metric, num, den, a / (a + b), iv.lo, iv.hi, "measured")


def _value(provider, segment, metric, value, failed) -> ProviderMetric:
    state = "failed" if failed else ("measured" if value is not None else "not_enough_data")
    return ProviderMetric(provider, segment, metric, None, None, None if failed else value, None, None, state)


def provider_metrics(
    providers: Iterable[str],
    trials: Iterable[KnownTrial],
    candidates: Iterable[Candidate],
    known_keys: set[str],
    kept_keys: set[str],
    reviewed_keys: set[str],
    calls: Iterable[ProviderCall],
    segment: str | None = None,
) -> list[ProviderMetric]:
    """Leaderboard metrics per provider (ADR 0015), optionally for one segment.

    Good finds = known ∪ kept. Only known or reviewed candidates count for precision and recall;
    candidates left out of the review sample are excluded. A provider whose every call errored is
    `failed`, never 0.
    """
    trials = [t for t in trials if segment is None or t.segment == segment]
    calls = [c for c in calls if segment is None or c.segment == segment]
    cands = [c for c in candidates if segment is None or segment in c.segments]
    eligible = {c.key for c in cands if c.key in known_keys or c.key in reviewed_keys}
    good = (known_keys | kept_keys) & eligible
    proposed = {p: {c.key for c in cands if p in c.providers} & eligible for p in providers}
    found_by_any = set().union(*proposed.values()) if proposed else set()
    all_good = good & found_by_any
    known_here = known_keys & {c.key for c in cands} if segment else known_keys

    out: list[ProviderMetric] = []
    for p in sorted(proposed):
        p_calls = [c for c in calls if c.provider == p]
        failed = bool(p_calls) and not any(c.ok for c in p_calls)
        p_trials = [t for t in trials if t.provider == p]
        hits = sum(t.hit for t in p_trials)
        out.append(_proportion(p, segment, "known_hit_rate", hits, len(p_trials), failed))
        mrr = (sum(1 / t.rank for t in p_trials if t.hit and t.rank) / len(p_trials)) if p_trials else None
        out.append(_value(p, segment, "known_mrr", mrr, failed))

        mine = proposed[p]
        good_mine = mine & good
        out.append(_proportion(p, segment, "precision", len(good_mine), len(mine), failed))
        out.append(_proportion(p, segment, "pooled_recall", len(good_mine), len(all_good), failed))
        out.append(_proportion(p, segment, "known_recall", len(mine & known_here), len(known_here), failed))
        others = set().union(*(proposed[q] for q in proposed if q != p)) if len(proposed) > 1 else set()
        out.append(_value(p, segment, "exclusive", float(len(good_mine - others)), failed))
        usd = sum(c.usd for c in p_calls)
        out.append(_value(p, segment, "usd_per_good_find", usd / len(good_mine) if good_mine else None, failed))
        lat = [c.latency_ms for c in p_calls if c.ok and c.latency_ms is not None]
        out.append(_value(p, segment, "latency_ms", median(lat) if lat else None, failed))
    return out
