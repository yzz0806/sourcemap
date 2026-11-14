"""Leadership-change signals — the sources side (US mega-cap: Nvidia, Apple, Microsoft).

Plan publisher categories, search through Telem, read the pages found, and extract the
appointments/departures each page reports, with the page's publication date. Search only finds
pages (R2); events are kept only when their quote is on the saved page.
"""

import json
import re

COMPANIES = {"nvidia": "Nvidia", "apple": "Apple", "microsoft": "Microsoft"}
PROVIDERS = ["exa", "you", "parallel", "brave"]
SKIP = ("sec.gov", "linkedin.com", "youtube.com", "facebook.com", "x.com", "twitter.com", "instagram.com",
        "reddit.com", "tiktok.com", "threads.net")

PLAN_PROMPT = """You plan where to search for sources that publish LEADERSHIP CHANGES (executive appointments
and departures, with dates) at companies in one segment. Plan categories of publishers (official filings,
company newsroom / investor-relations press releases, wire services, business news, tech and trade press,
crowd-edited org-chart sites, executive-move trackers, encyclopedias…) with 2 query TEMPLATES each using
the placeholder {company}. Do not name specific websites. Skip paid or login-only sources and say why.
Answer one JSON object only:
{"categories": [{"name": "...", "lineage": "...", "queries": ["... {company} ...", "..."]}],
 "skipped": [{"name": "...", "why": "..."}]}"""

EXTRACT_PROMPT = """From the page text, list the executive leadership changes at {company} that the page REPORTS
(appointments, departures, role changes of executives or officers). For each: person (full name), change
("appointed" | "departed" | "role_change"), role (the role gained or left), effective_date (as stated, else
null), and a short verbatim quote (under 200 characters) from the page that contains the person's name.
Only report what the page states; do not add background knowledge. If the page reports none, return [].
Answer one JSON object only: {{"events": [{{"person": "...", "change": "...", "role": "...", "effective_date": null, "quote": "..."}}]}}"""

_META = [
    ("article:published_time", r'<meta[^>]+(?:property|name)=["\']article:published_time["\'][^>]+content=["\']([^"\']+)'),
    ("article:published_time", r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']article:published_time'),
    ("datePublished", r'"datePublished"\s*:\s*"([^"]+)"'),
    ("time datetime", r'<time[^>]+datetime=["\']([^"\']+)'),
    ("og:updated_time", r'<meta[^>]+(?:property|name)=["\']og:updated_time["\'][^>]+content=["\']([^"\']+)'),
]


def published(html: str) -> tuple[str | None, str | None]:
    """The page's publication date from its metadata, and which field it came from."""
    for field, pat in _META:
        m = re.search(pat, html, re.I)
        if m and re.match(r"\d{4}-\d{2}-\d{2}", m.group(1).strip()):
            return m.group(1).strip()[:25], field
    return None, None


def skip_url(url: str) -> bool:
    u = url.lower()
    host = u.split("://", 1)[-1].split("/", 1)[0]
    return u.endswith(".pdf") or any(host == d or host.endswith("." + d) for d in SKIP)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().casefold()


def event_ok(ev: dict, text_norm: str) -> bool:
    q = norm(ev.get("quote", ""))
    parts = [p for p in norm(ev.get("person", "")).replace(".", " ").split() if len(p) > 1]
    surname = parts[-1] if parts else ""
    return bool(q) and q in text_norm and bool(surname) and surname in q


def pick_urls(rows: list[dict], company: str, cap: int = 40) -> list[dict]:
    """Unique URLs for a company, preferring URLs found by more providers, then better rank."""
    seen: dict[str, dict] = {}
    for row in rows:
        if row["company"] != company:
            continue
        for run in row["runs"]:
            for h in run["hits"]:
                u = h["url"].split("#")[0]
                if skip_url(u):
                    continue
                e = seen.setdefault(u, {"url": u, "providers": set(), "best_rank": 99})
                e["providers"].add(run["provider"])
                e["best_rank"] = min(e["best_rank"], h["rank"])
    ranked = sorted(seen.values(), key=lambda e: (-len(e["providers"]), e["best_rank"], e["url"]))
    return [{"url": e["url"], "found_by": sorted(e["providers"])} for e in ranked[:cap]]


def dumps(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=1, default=list)
