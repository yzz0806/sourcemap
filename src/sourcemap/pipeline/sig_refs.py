"""Leadership-change signals — the US reference: SEC 8-K Item 5.02 filings, one event per change.

Item 5.02 must be filed within four business days of a director/officer departure, appointment or
compensatory arrangement, so its filing date is the reference date for freshness. Helpers here are
pure (filtering, section cutting, event validation); I/O lives in scripts/sig_refs.py.
"""

import re

COMPANIES = {"nvidia": 1045810, "apple": 320193, "microsoft": 789019}
WINDOW = ("2024-11-01", "2026-11-14")

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
    """The Item 5.02 section: from 'Item 5.02' to the next 'Item N.NN' heading or the signature block."""
    m = re.search(r"item\s*5\.02", text, re.I)
    if not m:
        return text[:limit]
    rest = text[m.start():]
    end = re.search(r"\bitem\s*\d{1,2}\.\d{2}\b|\bsignatures?\b", rest[12:], re.I)
    section = rest[: 12 + end.start()] if end else rest
    return section[:limit]


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("’", "'").replace("“", '"').replace("”", '"')).strip().casefold()


def valid_event(ev: dict, section: str) -> bool:
    """Keep only events whose quote is in the section and names the person (surname)."""
    q, name = _norm(ev.get("quote", "")), (ev.get("person") or "").strip()
    if not q or not name or ev.get("change") not in ("appointed", "departed", "role_change"):
        return False
    surname = _norm(name.split()[-1]).strip(".,")
    return q in _norm(section) and surname in q
