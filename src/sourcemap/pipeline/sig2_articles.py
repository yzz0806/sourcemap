"""Leadership-change signals v2 — article sources checked against every filed change.

For each (filed 8-K Item 5.02 change × source) — sources: the company's newsroom, two press-release wires,
a wire mirror and eleven news sites — locate a page with a Telem search restricted to the source's site
(search only *finds*, R2), read the page politely (raw saved), extract the changes it reports (judge, verbatim
quotes checked), and decide with sig_measure.match_event against that filed change.
Output records follow the contract in pipeline/sig2_measure.py.
"""

import re

SOURCES = ["newsroom", "businesswire.com", "prnewswire.com", "stocktitan.net",
           "reuters.com", "apnews.com", "bloomberg.com", "cnbc.com", "foxbusiness.com", "fortune.com",
           "businessinsider.com", "nytimes.com", "techcrunch.com", "theverge.com"]
VERB = {"appointed": "appointed", "departed": "steps down", "role_change": "named"}


def site_prefix(source: str, newsroom: str) -> str:
    """host[/path] the source lives on, without scheme or www (newsroom: the company's newsroom prefix)."""
    raw = newsroom if source == "newsroom" else source
    raw = re.sub(r"^https?://", "", raw.strip().lower()).removeprefix("www.")
    return raw.rstrip("/")


def on_site(url: str, prefix: str) -> bool:
    u = re.sub(r"^https?://", "", url.strip().lower()).removeprefix("www.")
    host, _, path = u.partition("/")
    p_host, _, p_path = prefix.partition("/")
    host_ok = host == p_host or host.endswith("." + p_host)
    return host_ok and (not p_path or path.startswith(p_path))


def query(ev: dict, company_name: str, prefix: str) -> str:
    return f'"{ev["person"]}" {company_name} {VERB.get(ev["change"], "named")} site:{prefix}'
