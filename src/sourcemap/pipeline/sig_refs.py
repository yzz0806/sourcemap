"""Leadership-change signals — the US reference: SEC 8-K Item 5.02 filings, one event per change.

Item 5.02 must be filed within four business days of a director/officer departure, appointment or
compensatory arrangement, so its filing date is the reference date for freshness. Helpers here are
pure (filtering, section cutting, event validation); I/O lives in scripts/sig_refs.py.
"""

import re

COMPANIES = {"nvidia": 1045810, "apple": 320193, "microsoft": 789019}
WINDOW = ("2024-11-01", "2026-11-14")

# Expanded reference (data/sig2): ten US mega-caps over five years.
WINDOW2 = ("2021-11-14", "2026-11-14")
COMPANIES2 = {
    "nvidia": {"cik": 1045810, "name": "Nvidia", "ticker": "NVDA", "domain": "nvidia.com",
               "newsroom": "https://nvidianews.nvidia.com/", "wikipedia": "Nvidia"},
    "apple": {"cik": 320193, "name": "Apple", "ticker": "AAPL", "domain": "apple.com",
              "newsroom": "https://www.apple.com/newsroom/", "wikipedia": "Apple Inc."},
    "microsoft": {"cik": 789019, "name": "Microsoft", "ticker": "MSFT", "domain": "microsoft.com",
                  "newsroom": "https://news.microsoft.com/", "wikipedia": "Microsoft"},
    "alphabet": {"cik": 1652044, "name": "Alphabet", "ticker": "GOOGL", "domain": "abc.xyz",
                 "newsroom": "https://abc.xyz/investor/", "wikipedia": "Alphabet Inc."},
    "amazon": {"cik": 1018724, "name": "Amazon", "ticker": "AMZN", "domain": "amazon.com",
               "newsroom": "https://press.aboutamazon.com/", "wikipedia": "Amazon (company)"},
    "meta": {"cik": 1326801, "name": "Meta Platforms", "ticker": "META", "domain": "meta.com",
             "newsroom": "https://about.fb.com/news/", "wikipedia": "Meta Platforms"},
    "tesla": {"cik": 1318605, "name": "Tesla", "ticker": "TSLA", "domain": "tesla.com",
              "newsroom": "https://ir.tesla.com/", "wikipedia": "Tesla, Inc."},
    "broadcom": {"cik": 1730168, "name": "Broadcom", "ticker": "AVGO", "domain": "broadcom.com",
                 "newsroom": "https://investors.broadcom.com/", "wikipedia": "Broadcom"},
    "jpmorgan": {"cik": 19617, "name": "JPMorgan Chase", "ticker": "JPM", "domain": "jpmorganchase.com",
                 "newsroom": "https://www.jpmorganchase.com/newsroom", "wikipedia": "JPMorgan Chase"},
    "eli-lilly": {"cik": 59478, "name": "Eli Lilly", "ticker": "LLY", "domain": "lilly.com",
                  "newsroom": "https://investor.lilly.com/", "wikipedia": "Eli Lilly and Company"},
}

EXTRACT_PROMPT = """From this Item 5.02 section of an SEC Form 8-K, list every change it reports.
For each change give:
- person: the full name as written
- change: "appointed" (new to the role or board), "departed" (leaving, retiring, resigning, not standing
  for re-election), or "role_change" (an existing officer/director moves to a different role)
- role: the title or board role concerned
- kind: "officer", "director", or "compensation_only" (only a pay/award/plan change, no move)
- effective_date: YYYY-MM-DD if the text states it, else null
- quote: one verbatim sentence from the text that states the change and contains the person's name
Do not invent anything; if the section reports no person, return an empty list.
Answer one JSON object only: {"events": [{"person": "...", "change": "...", "role": "...", "kind": "...", "effective_date": null, "quote": "..."}]}"""


def filings_in_window(sub: dict, window=WINDOW) -> list[dict]:
    """8-K / 8-K/A filings whose items include 5.02, filed inside the window. `sub` is a filings.recent
    (or extra file) dict of parallel arrays."""
    out = []
    for i, form in enumerate(sub.get("form", [])):
        if form not in ("8-K", "8-K/A"):
            continue
        items, date = sub["items"][i] or "", sub["filingDate"][i]
        if "5.02" in items and window[0] <= date <= window[1]:
            out.append({"form": form, "accession": sub["accessionNumber"][i], "filing_date": date,
                        "report_date": sub.get("reportDate", [None] * len(sub["form"]))[i],
                        "primary": sub["primaryDocument"][i], "items": items})
    return out


def doc_url(cik: int, accession: str, primary: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession.replace('-', '')}/{primary}"


def cut_502(text: str, limit: int = 12000) -> str:
    """The Item 5.02 section: from 'Item 5.02' to the next 'Item N.NN' heading or the signature block.
    Some filings (Amazon) open with a table of contents that also says 'Item 5.02 … 3', so every
    occurrence is cut and the longest section wins."""
    best = ""
    for m in re.finditer(r"item\s*5\.02", text, re.I):
        rest = text[m.start():]
        end = re.search(r"\bitem\s*\d{1,2}\.\d{2}\b|\bsignatures?\b", rest[12:], re.I)
        section = rest[: 12 + end.start()] if end else rest
        if len(section) > len(best):
            best = section
    return best[:limit] if best else text[:limit]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("“", '"').replace("”", '"')).strip().casefold()


def dedupe_events(events: list[dict], norm_key) -> list[dict]:
    """One event per (normalised person, change, filing month); compensation-only items dropped.
    `norm_key(name)` gives a comparable person key (measure.names.normalise_name(...).key)."""
    seen, out = set(), []
    for e in sorted(events, key=lambda e: (e["filing_date"], e["id"])):
        if e.get("kind") == "compensation_only":
            continue
        k = (e["company"], norm_key(e["person"]), e["change"], e["filing_date"][:7])
        if k not in seen:
            seen.add(k)
            out.append(e)
    return out


def valid_event(ev: dict, section: str) -> bool:
    """Keep only events whose quote is in the section and names the person (surname)."""
    q, name = _norm(ev.get("quote", "")), (ev.get("person") or "").strip()
    if not q or not name or ev.get("change") not in ("appointed", "departed", "role_change"):
        return False
    surname = _norm(name.split()[-1]).strip(".,")
    return q in _norm(section) and surname in q
