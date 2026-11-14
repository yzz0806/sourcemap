"""Benchmark case tables — the specification of measure.benchmark (ADR 0015, docs/domain.md §10).

Plain-language rows: URL normalising, known-answer scoring, collapsing hits into candidates, and a
two-provider scenario with expected metrics.
"""

# (name, raw url, expected normalised url)
NORMALISE_URL_CASES = [
    ("scheme and www dropped", "https://www.theorg.com/org/gong", "theorg.com/org/gong"),
    ("trailing slash dropped", "http://theorg.com/org/gong/", "theorg.com/org/gong"),
    ("query and fragment dropped", "https://theorg.com/org/gong?utm=x#team", "theorg.com/org/gong"),
    ("host lowercased, path kept", "HTTPS://TheOrg.COM/org/Gong", "theorg.com/org/Gong"),
    ("port dropped", "https://ror.org:443/04t5xt781", "ror.org/04t5xt781"),
    ("bare host", "https://www.gong.io", "gong.io"),
]

# (name, expected url, hits in rank order, expected (hit, rank))
KNOWN_ANSWER_CASES = [
    ("exact match at rank 2", "https://theorg.com/org/gong",
     ["https://gong.io", "https://www.theorg.com/org/gong/", "https://linkedin.com/company/gong"], (True, 2)),
    ("deeper page of the expected one counts", "https://theorg.com/org/gong",
     ["https://theorg.com/org/gong/teams/sales"], (True, 1)),
    ("a sibling page with a longer slug does not count", "https://theorg.com/org/gong",
     ["https://theorg.com/org/gongio"], (False, None)),
    ("not returned at all", "https://ror.org/04t5xt781",
     ["https://en.wikipedia.org/wiki/Purdue_University"], (False, None)),
    ("no hits", "https://ror.org/04t5xt781", [], (False, None)),
]

# (name, url, expected candidate key = registrable domain + "/" + first path segment)
CANDIDATE_KEY_CASES = [
    ("subdomain collapses to registrable domain", "https://careers.gong.io/jobs/1", "gong.io/jobs"),
    ("theorg org pages collapse to one source", "https://theorg.com/org/airtable", "theorg.com/org"),
    ("Korean second-level suffix keeps three labels", "https://dart.fss.or.kr/dsab007/main.do",
     "fss.or.kr/dsab007"),
    ("Korean university", "https://cs.kaist.ac.kr/people/faculty", "kaist.ac.kr/people"),
    ("UK second-level suffix", "https://www.example.co.uk/about", "example.co.uk/about"),
    ("bare domain has empty first segment", "https://www.gong.io/", "gong.io/"),
]

# Two-provider scenario for provider_metrics. Candidates are keys; good finds = kept + known.
# provider "a" proposed k1 k2 k3 k4 k5 k6; provider "b" proposed k1 k7 k8.
# known: k1 (seed source). kept at blind review: k2 k3 k7. rejected: k4 k5 k8. k6 not sampled.
SCENARIO = {
    "proposed": {"a": ["k1", "k2", "k3", "k4", "k5", "k6"], "b": ["k1", "k7", "k8"]},
    "known": {"k1"},
    "kept": {"k2", "k3", "k7"},
    "reviewed": {"k2", "k3", "k4", "k5", "k7", "k8"},
    # expected (num, den) per provider
    "precision": {"a": (3, 5), "b": (2, 3)},        # k6 unreviewed → excluded from a's denominator
    "pooled_recall": {"a": (3, 4), "b": (2, 4)},    # all good finds: k1 k2 k3 k7
    "known_recall": {"a": (1, 1), "b": (1, 1)},
    "exclusive": {"a": 2, "b": 1},                  # a: k2 k3; b: k7
}
