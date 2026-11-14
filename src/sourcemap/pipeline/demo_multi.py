"""Multi-segment source benchmark (demo): plan → search (Telem) → pick sources → read → verify
against each segment's reference → score accuracy, coverage and cost per source.

Segments and references (docs/plan/demo-samsung-marketing.md, extended 2026-11-14):
  Korean listed · Samsung Electronics · DART 2025 annual report (official filing, tier 1)
  US large      · Nvidia             · nvidianews.nvidia.com/bios (company's own page, tier 2)
  European      · Airbus             · airbus.com executive & operational committees (own page, tier 2)
Rules: search results only find sources (R2); every extracted person must quote text found on the
saved page; every match quotes the reference row; accuracy uses the stage 1 Beta rules (ADR 0002).
"""

import html as htmllib
import json
import re
from collections import defaultdict

from sourcemap.domain.model import Verification
from sourcemap.domain.vocab import Method, Tier, Verdict
from sourcemap.measure.accuracy import estimate, prior_for
from sourcemap.measure.benchmark import registrable_domain

COMPANIES = {
    "samsung-electronics": {"name": "Samsung Electronics", "segment": "Korean listed", "country": "South Korea",
                            "own_domains": ["samsung.com", "samsungsemiconductor.com"], "reference": "DART"},
    "nvidia": {"name": "Nvidia", "segment": "US large", "country": "United States",
               "own_domains": ["nvidia.com"], "reference": "https://nvidianews.nvidia.com/bios"},
    "airbus": {"name": "Airbus", "segment": "European large", "country": "France / Netherlands",
               "own_domains": ["airbus.com"],
               "reference": "https://www.airbus.com/en/about-us/our-governance/executive-and-operational-committees"},
}
PROVIDERS = ["exa", "you", "parallel", "brave"]
NOT_SOURCES = {"linkedin.com", "youtube.com", "facebook.com", "x.com", "twitter.com", "instagram.com",
               "reddit.com", "fss.or.kr", "google.com", "bing.com",
               "sec.gov"}  # sec.gov is the US reference, not a source under test
TIER3 = {"theorg.com", "wikipedia.org", "crunchbase.com", "bloomberg.com", "reuters.com", "forbes.com"}

PLAN_PROMPT = """You plan where to search for the sources that publish a company's leadership / org chart
(who holds which executive role, and who reports to whom). Plan categories of publishers (official
filings in the company's home country, the company's own pages, crowd-edited org-chart sites,
news, business/executive databases, encyclopedias…) and 2 search queries per category, in the
language those publishers use. Do not name specific websites. Skip paid or login-only sources.
Answer one JSON object only: {"categories": [{"name": "...", "lineage": "...", "queries": ["...", "..."]}]}"""

EXTRACT_PROMPT = """From the page text, list the people the page presents as CURRENT leaders or employees of
{company}, with the title the page gives them. For each, copy a short verbatim quote (under 200
characters) from the page text that contains the person's name. Do not add anyone not on the page,
do not infer titles. If the page lists nobody, return an empty list.
Answer one JSON object only: {{"people": [{{"name": "...", "title": "...", "quote": "..."}}]}}"""

MATCH_PROMPT = """You match people from a source (List A) to a reference list (List B) for {company} and judge titles.
List B: {ref_desc}
For EACH person in List A: find the List B row that is the same person (names may be romanized or
spelled differently, e.g. 조성혁 = Seong H. Cho). If several rows could match, or none does, answer
null — a wrong match is worse than none. If matched, judge whether A's title is consistent with B's
rank/title/responsibility: "consistent", "inconsistent" or "unclear". Quote the B row exactly.
Answer one JSON object only:
{{"matches": [{{"a": <A index>, "b": <B index or null>, "b_quote": "...", "title": "consistent|inconsistent|unclear|null", "reason": "..."}}]}}"""


def html_to_text(html: str, limit: int = 60000) -> str:
    html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
    text = htmllib.unescape(re.sub(r"<[^>]+>", " ", html))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip().casefold()


def quote_ok(person: dict, text_norm: str) -> bool:
    """The quote must be on the page and contain (part of) the name."""
    q = norm(person.get("quote", ""))
    name_parts = [p for p in norm(person.get("name", "")).split() if len(p) > 1]
    return bool(q) and q in text_norm and any(p in q for p in name_parts)


def host(url: str) -> str:
    return url.split("://", 1)[-1].split("/", 1)[0].split(":")[0].lower().removeprefix("www.")


def source_key(url: str) -> str:
    h = host(url)
    return "theorg.com" if h.endswith("theorg.com") else registrable_domain(h)


def tier_of(key: str, company: dict) -> Tier:
    if any(key.endswith(d) for d in company["own_domains"]):
        return Tier.FIRST_PARTY
    if key in TIER3 or key.endswith("wikipedia.org"):
        return Tier.RESEARCHED
    return Tier.AGGREGATE  # unknown aggregators: weakest prior until measured


def pick_sources(search: dict, min_companies: int = 2, top: int = 6, companies: dict | None = None) -> list[dict]:
    """Domains that came up for at least `min_companies` companies, minus each company's own domains
    (they are, or stand in for, the reference) and social/login sites. Per company, the URL that
    was returned most often (best rank as tie-break)."""
    seen = defaultdict(lambda: defaultdict(list))  # key -> company -> [(rank, url)]
    for row in search["rows"]:
        own = (companies or COMPANIES)[row["company"]]["own_domains"]
        for run in row["runs"]:
            for h in run["hits"]:
                k = source_key(h["url"])
                if k in NOT_SOURCES or any(k.endswith(d) for d in own) or h["url"].lower().endswith(".pdf"):
                    continue
                seen[k][row["company"]].append((h["rank"], h["url"]))
    ranked = sorted(seen.items(), key=lambda kv: (-len(kv[1]), -sum(len(v) for v in kv[1].values()), kv[0]))
    out = []
    for k, per in ranked:
        if len(per) < min_companies:
            continue
        urls = {}
        for c, hits in per.items():
            # Prefer URLs that name the company (a Wikipedia hit for "Hercules" is not Airbus's page).
            token = (companies or COMPANIES)[c].get("url_token", c.split("-")[0])
            hits = [(r, u) for r, u in hits if token in u.lower()]
            if not hits:
                continue  # only unrelated pages from this source: not found for this company
            counts = defaultdict(lambda: [0, 99])
            for rank, u in hits:
                counts[u][0] += 1
                counts[u][1] = min(counts[u][1], rank)
            urls[c] = max(counts.items(), key=lambda kv: (kv[1][0], -kv[1][1]))[0]
        out.append({"key": k, "companies": sorted(per), "urls": urls, "hits": sum(len(v) for v in per.values())})
        if len(out) >= top:
            break
    return out


def search_cost_by_source(search: dict) -> dict:
    """Each provider call's cost split equally over its hits; summed per (source, company)."""
    cost = defaultdict(float)
    for row in search["rows"]:
        for run in row["runs"]:
            if run["hits"]:
                share = run["usd"] / len(run["hits"])
                for h in run["hits"]:
                    cost[(source_key(h["url"]), row["company"])] += share
    return cost


def verdicts(people: list[dict], ref: list[dict], matches: list[dict], ref_complete: bool) -> list[dict]:
    """Employment/title verdicts per extracted person. A person absent from a reference that lists
    only top leaders (ref_complete=False), or only executives (DART), is unverifiable, not wrong."""
    by_a = {m.get("a"): m for m in matches}
    out = []
    for i, p in enumerate(people):
        m = by_a.get(i) or {}
        b = m.get("b")
        ok = isinstance(b, int) and 0 <= b < len(ref) and m.get("b_quote")
        if ok:
            emp = "correct"
            title = {"consistent": "correct", "inconsistent": "wrong"}.get(m.get("title"), "unverifiable")
        else:
            emp = title = "unverifiable"
        out.append({"person": p, "ref_index": b if ok else None, "ref_row": ref[b] if ok else None,
                    "ref_quote": m.get("b_quote", "") if ok else "", "employment": emp, "title": title,
                    "reason": m.get("reason", "")})
    return out


def score(checks: list[dict], tier: Tier) -> dict:
    prior = prior_for(tier)
    out = {}
    for ct in ("employment", "title"):
        vs = [Verification(i, Method.REFERENCE, Verdict(c[ct]), _T0) for i, c in enumerate(checks)]
        e = estimate(vs, prior)
        out[ct] = {"state": e.state.value, "mean": e.mean,
                   "interval": [e.interval.lo, e.interval.hi] if e.interval else None,
                   "n": e.n_decisive, "n_correct": e.n_correct, "n_wrong": e.n_wrong,
                   "unverifiable_share": e.unverifiable_share, "prior": list(prior)}
    return out


def top_reference(company_slug: str, ref: list[dict]) -> list[int]:
    """Indexes of the 'top leadership' used for comparable coverage: for DART, ranks 회장/부회장/사장
    plus registered directors' table rows; for own-page references, everyone listed."""
    if company_slug != "samsung-electronics":
        return list(range(len(ref)))
    return [i for i, r in enumerate(ref) if r.get("title") in ("회장", "부회장", "사장", "대표이사")]


from datetime import datetime  # noqa: E402

_T0 = datetime(2026, 11, 14)
