"""Segment references for the marketing org-chart benchmark: what "verified" means per segment.

  kr_listed — DART annual report (official filing, tier 1): all executives + registered directors.
  us_listed — SEC 10-K "Information about our Executive Officers" (official filing, tier 1).
  eu_listed — the company's own executive board / leadership page (tier 2).
Every extracted row carries a verbatim quote that must appear in the saved source text.
"""

import re

MARKETING = re.compile(r"마케팅|marketing|\bMKT\b|\bCMO\b|brand", re.I)

SEC_PROMPT = """From this section of a 10-K, list every executive officer with their title exactly as stated.
For each, copy a short verbatim quote (under 200 characters) from the text that contains the
person's name. Do not add anyone not in the text. Answer one JSON object only:
{"people": [{"name": "...", "title": "...", "quote": "..."}]}"""


def is_marketing(row: dict) -> bool:
    text = f"{row.get('title', '')} {row.get('responsibility', '')}"
    if re.search(r"communications", text, re.I) and not re.search(r"marketing", text, re.I):
        return False
    return bool(MARKETING.search(text))


def marketing_idx(rows: list[dict]) -> list[int]:
    return [i for i, r in enumerate(rows) if is_marketing(r)]


def _person_score(seg: str) -> int:
    """How person-like a passage is: ages ("Ms. Adams, 61," / "Age 58"), officer titles."""
    return len(re.findall(r"\bAge\b|\bage \d{2}\b|, \d{2},|\b\d{2}\s+(?:President|Chief|Executive|Senior)"
                          r"|Senior Vice President|Executive Vice President|Chief \w+ Officer", seg))


def exec_officer_section(text: str, limit: int = 12000) -> str:
    """The filing passage listing executive officers: of every heading-like occurrence, the one
    followed by the most person-like content (10-K "Information about our Executive Officers", or
    a proxy statement's "Executive Officers" pages)."""
    best, best_score = "", 0
    for m in re.finditer(r"executive officers", text, re.I):
        seg = text[m.start(): m.start() + limit]
        sc = _person_score(seg)
        if sc > best_score:
            best, best_score = seg, sc
    return best if best_score >= 3 else ""


def _cells(tr: str) -> list[str]:
    return [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
            for c in re.findall(r"<T[DEHU][^>]*>(.*?)</T[DEHU]>", tr, re.S | re.I)]


BIRTH = re.compile(r"^\d{4}(?:\.\d{2}|년\s*\d{1,2}월)$")


def parse_exec_rows_flex(xml: str) -> list[dict]:
    """DART executive rows across filers' layouts: name | sex | birth (YYYY.MM or YYYY년 MM월) |
    rank | [registered?] | 상근/비상근 | responsibility … (some filers add a column before 상근;
    some use <TU> cells)."""
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", xml, re.S | re.I):
        c = _cells(tr)
        if len(c) < 6 or c[1] not in ("남", "여") or not BIRTH.match(c[2]):
            continue
        j = next((k for k in range(4, min(len(c), 8)) if c[k] in ("상근", "비상근")), None)
        resp = c[j + 1] if j is not None and j + 1 < len(c) else (c[5] if len(c) > 5 else "")
        rows.append({"name": c[0], "title": c[3], "responsibility": resp, "quote": ""})
    return rows


def dedupe(rows: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in rows:
        k = (r["name"], r["title"], r["responsibility"])
        if k not in seen:
            seen.add(k)
            out.append(r)
    return out
