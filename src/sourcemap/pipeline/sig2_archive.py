"""Leadership-change signals v2 — archive-measured sources (pages that list a company's current people).

For every filed change (data/sig2/refs.json) × source in SOURCES, use Internet Archive (Wayback) snapshots
of the source's page for that company to find the first capture after the 8-K filing that reflects the
change: appointed / role change → the person is shown; departed → the person is no longer shown.
Freshness is bounded by how often the Archive captured the page, so each check records bound_days.
Wikipedia's API is disallowed by its robots.txt, so Wikipedia too is read only through Wayback captures.

Search (Telem) is used once per company only to *locate* the MarketScreener and theorg pages (R2: never
evidence). Evidence for every verdict is a Wayback snapshot URL.
"""

import hashlib
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from sourcemap.pipeline.demo_multi import html_to_text
from sourcemap.sandbox.kit import BlockedByRobots, FetchError, Kit

SOURCES = ["wikipedia.org", "finance.yahoo.com", "marketscreener.com", "theorg.com"]
TOP_ROLE = re.compile(r"\b(ceo|chief executive|chair|chairman|chairwoman|cfo|chief financial)\b|(?<!vice )\bpresident\b", re.I)
ALIASES = {"jen-hsun": ["jensen"]}  # legal vs used first names
CDX = "http://web.archive.org/cdx/search/cdx"
RANGE = ("20210901", "20261114")


def _key(s: str) -> str:
    return hashlib.sha1(s.encode()).hexdigest()


class Archive:
    """Polite, cached access to Wayback CDX listings and snapshot texts."""

    def __init__(self, cache: Path, kit: Kit):
        self.cache = cache
        (cache / "cdx").mkdir(parents=True, exist_ok=True)
        (cache / "pages").mkdir(parents=True, exist_ok=True)
        self.kit = kit
        self.requests = 0

    def snapshots(self, page: str) -> list[str]:
        f = self.cache / "cdx" / (_key(page) + ".json")
        if f.exists():
            return json.loads(f.read_text())
        r = self.kit.get(CDX, params={"url": page, "from": RANGE[0], "to": RANGE[1], "output": "json",
                                      "fl": "timestamp,statuscode", "filter": "statuscode:200", "collapse": "timestamp:8"})
        self.requests += 1
        rows = json.loads(r.text() or "[]") if r.status == 200 else []
        ts = [row[0] for row in rows[1:]] if rows else []
        f.write_text(json.dumps(ts))
        return ts

    def text(self, page: str, ts: str) -> str | None:
        url = f"https://web.archive.org/web/{ts}id_/{page}"
        f = self.cache / "pages" / (_key(url) + ".txt")
        if f.exists():
            t = f.read_text()
            return None if t == "\x00FAILED" else t
        try:
            r = self.kit.get(url)
            self.requests += 1
            t = html_to_text(r.text(), limit=400000) if r.status == 200 else None
        except (FetchError, BlockedByRobots, OSError):
            t = None
        f.write_text(t if t is not None else "\x00FAILED")
        return t


def tsdate(ts: str) -> date:
    return datetime.strptime(ts[:8], "%Y%m%d").date()


def shows(text: str, person: str) -> bool:
    """The person is on the page: surname and (first given name, an alias of it, or its initial + surname)."""
    t = " " + re.sub(r"[^\w\s-]", " ", text.lower()) + " "
    toks = [x for x in re.sub(r"[.,]", " ", person.lower()).split() if x]
    if not toks:
        return False
    sur = toks[-1]
    given = next((x for x in toks[:-1] if len(x.rstrip(".")) > 1), None)
    if not re.search(rf"\b{re.escape(sur)}\b", t):
        return False
    if not given:
        return True
    names = [given, *ALIASES.get(given, [])]
    if any(re.search(rf"\b{re.escape(g)}\b", t) for g in names):
        return True
    return bool(re.search(rf"\b{re.escape(given[0])}\.?\s+{re.escape(sur)}\b", t))


def applicable(source: str, ev: dict) -> tuple[bool, str]:
    if source == "finance.yahoo.com" and ev.get("kind") == "director":
        return False, "Yahoo Finance profile lists key executives only"
    if source == "wikipedia.org" and not TOP_ROLE.search(ev.get("role") or ""):
        return False, "Wikipedia infobox lists only top roles (CEO, chair, president, CFO)"
    return True, ""


def check(arc: Archive, source: str, page: str | None, ev: dict) -> dict:
    out = {"event_id": ev["id"], "company": ev["company"], "source": source, "status": None, "verdict": None,
           "date": None, "days_late": None, "bound_days": None, "url": page, "evidence": None, "quote": "", "reason": "", "usd": 0.0}
    ok, why = applicable(source, ev)
    if not ok:
        return {**out, "status": "not_tracked", "reason": why}
    if not page:
        return {**out, "status": "not_tracked", "reason": "page not located"}
    F = date.fromisoformat(ev["filing_date"])
    lo, hi = F - timedelta(days=60), F + timedelta(days=365)
    try:
        snaps = [s for s in arc.snapshots(page) if lo <= tsdate(s) <= hi]
    except (FetchError, BlockedByRobots, OSError) as e:
        return {**out, "status": "error", "reason": f"CDX: {type(e).__name__}"}
    pre = [s for s in snaps if tsdate(s) < F]
    post = [s for s in snaps if tsdate(s) >= F]
    want_shown = ev["change"] != "departed"          # what the page shows once it reflects the change

    def reflects(ts):
        tx = arc.text(page, ts)
        return None if tx is None else (shows(tx, ev["person"]) == want_shown)

    base = None
    for s in reversed(pre):                          # last readable capture before the filing
        r = reflects(s)
        if r is not None:
            base = (s, r)
            break
    if base is None and post:
        r = reflects(post[0])
        if r is False:
            base, post = (post[0], False), post[1:]
        elif r is None:
            return {**out, "status": "error", "reason": "baseline capture unreadable"}
        else:
            return {**out, "status": "not_tracked", "reason": "no baseline: no capture before the filing in the window"}
    if base is None:
        return {**out, "status": "not_tracked", "reason": "no captures in the window"}
    if base[1]:
        why = "already listed before the filing" if want_shown else "person not on the page before the filing"
        return {**out, "status": "not_tracked", "reason": why, "evidence": f"https://web.archive.org/web/{base[0]}/{page}"}
    if not post:
        return {**out, "status": "not_tracked", "reason": "no captures after the filing in the window"}
    # binary search: first capture ≥ F that reflects the change (assumed monotonic)
    lo_i, hi_i, first = 0, len(post) - 1, None
    last_r = reflects(post[-1])
    if not last_r:
        return {**out, "status": "not_found", "reason": "no capture within a year of the filing reflects the change",
                "evidence": f"https://web.archive.org/web/{post[-1]}/{page}"}
    while lo_i <= hi_i:
        mid = (lo_i + hi_i) // 2
        r = reflects(post[mid])
        if r:
            first, hi_i = mid, mid - 1
        else:
            lo_i = mid + 1
    first = post[first if first is not None else len(post) - 1]
    before = [s for s in post if s < first]
    last_not = before[-1] if before else base[0]
    d = tsdate(first)
    return {**out, "status": "found", "verdict": "correct", "date": d.isoformat(), "days_late": (d - F).days,
            "bound_days": [(tsdate(last_not) - F).days, (d - F).days],
            "evidence": f"https://web.archive.org/web/{first}/{page}"}
