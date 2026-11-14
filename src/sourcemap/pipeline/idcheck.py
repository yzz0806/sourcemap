"""Automatic checks that every seeded identifier is real (docs/plan/stage-2-storage-and-seed.md).

Stage 3's known-answer benchmark (ADR 0015) uses only identifiers that pass. Checks go through a
`fetch(url)` callable — the polite kit in real use, a fake in tests. The DART key is sent to the
DART API only and never written into a result's detail.
"""

import json
import re
import sqlite3
import unicodedata
from collections.abc import Callable, Iterable
from datetime import datetime

from sourcemap.sandbox.kit import BlockedByRobots, FetchError, RawResponse

Fetch = Callable[..., RawResponse]

KINDS_ORG = ("theorg", "linkedin", "dart_corp_code", "people_page")
KINDS_ACADEMIC = ("ror", "openalex_institution", "people_page")
LINKEDIN_COMPANY = re.compile(r"^https://(www\.)?linkedin\.com/company/[^/?#]+/?$")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).casefold()
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^\w]+", " ", s).strip()


def _mentions(text: str, terms: Iterable[str]) -> bool:
    folded = f" {_fold(text)} "
    return any(t and f" {_fold(t)} " in folded for t in terms)


def _get(fetch: Fetch, url: str) -> tuple[RawResponse | None, str | None]:
    try:
        r = fetch(url)
    except BlockedByRobots:
        return None, "blocked_by_robots"
    except (FetchError, OSError) as e:
        return None, f"unreachable: {type(e).__name__}"
    if r.status != 200:
        return None, f"unreachable: HTTP {r.status}"
    return r, None


def check_identifier(kind: str, value: str | None, unit_name: str, *, fetch: Fetch, dart_key: str | None = None,
                     aliases: Iterable[str] = (), others: dict | None = None) -> tuple[str, str]:
    """Check one identifier. Returns (result, detail); results as in the identifier_check table."""
    if not value:
        return "missing", "no value in the seed"
    terms = (unit_name, *aliases)
    others = others or {}

    if kind == "linkedin":  # LinkedIn blocks automated fetches; a paid check isn't worth it here.
        return ("format_ok", "company URL shape") if LINKEDIN_COMPANY.match(value) else ("bad_format", value)

    if kind == "theorg":
        r, err = _get(fetch, f"https://theorg.com/org/{value}")
        if err:
            return err.split(":")[0], err
        title = re.search(r"<title[^>]*>(.*?)</title>", r.text(), re.S | re.I)
        title_text = title.group(1) if title else r.text()[:2000]
        return ("ok", f"title: {title_text.strip()[:80]}") if _mentions(title_text, terms) \
            else ("mismatch", f"title: {title_text.strip()[:80]}")

    if kind == "dart_corp_code":
        if not dart_key:
            return "no_key", "OPENDART_API_KEY not set"
        r, err = _get(fetch, f"https://opendart.fss.or.kr/api/company.json?crtfc_key={dart_key}&corp_code={value}")
        if err:
            return err.split(":")[0], err.replace(dart_key, "***")
        body = json.loads(r.text())
        if body.get("status") != "000":
            return "mismatch", f"DART status {body.get('status')}: {body.get('message', '')}"
        names = [body.get("corp_name", ""), body.get("corp_name_eng", ""), body.get("stock_name", "")]
        ok = any(_mentions(n, terms) for n in names) or any(_mentions(t, names) for t in terms)
        return ("ok" if ok else "mismatch"), f"DART: {body.get('corp_name')} / {body.get('corp_name_eng')}"

    if kind == "ror":
        r, err = _get(fetch, f"https://api.ror.org/v2/organizations/{value}")
        if err:
            return err.split(":")[0], err
        names = [n.get("value", "") for n in json.loads(r.text()).get("names", [])]
        ok = any(_mentions(n, terms) for n in names) or any(_mentions(t, names) for t in terms)
        return ("ok" if ok else "mismatch"), f"ROR names: {', '.join(names[:3])}"

    if kind == "openalex_institution":
        r, err = _get(fetch, f"https://api.openalex.org/institutions/{value}")
        if err:
            return err.split(":")[0], err
        body = json.loads(r.text())
        ror = (body.get("ror") or "").rstrip("/").rsplit("/", 1)[-1]
        expected = others.get("ror")
        if not expected:
            return "mismatch", f"no ROR to compare (OpenAlex says {ror})"
        return ("ok" if ror == expected else "mismatch"), f"OpenAlex {body.get('display_name')} ror={ror}"

    if kind == "people_page":
        r, err = _get(fetch, value)
        if err:
            return err.split(":")[0], err
        return ("ok", "page names the unit") if _mentions(r.text(), terms) else ("mismatch", "unit name not on page")

    return "missing", f"no check for kind {kind}"


def unit_terms(name: str, identifiers: dict) -> tuple[str, list[str]]:
    """The names a page or record may use for a unit: the company name, or the institution's name
    and acronym. The department name alone is too generic to prove a page is the right one."""
    base = identifiers.get("institution") or name.split("·")[0].strip()
    aliases = [name, *identifiers.get("aliases", [])]
    acronym = "".join(w[0] for w in base.split() if w[0].isupper())
    if len(acronym) >= 3:
        aliases.append(acronym)
    return base, [a for a in aliases if a]


def run_checks(conn: sqlite3.Connection, fetch: Fetch, *, now: datetime, dart_key: str | None = None,
               only_units: Iterable[str] | None = None) -> list[tuple[str, str, str, str, str]]:
    """Check every identifier of every unit and store the results. Returns rows
    (unit slug, kind, value, result, detail)."""
    out = []
    rows = conn.execute(
        "SELECT u.id, u.slug, u.name, u.identifiers_json, d.slug AS dt, s.slug AS segment FROM probe_unit u "
        "JOIN data_type d ON d.id = u.data_type_id JOIN panel_member pm ON pm.probe_unit_id = u.id "
        "JOIN segment s ON s.id = pm.segment_id ORDER BY d.slug DESC, u.id").fetchall()
    for row in rows:
        if only_units and row["slug"] not in set(only_units):
            continue
        ids = json.loads(row["identifiers_json"])
        base, aliases = unit_terms(row["name"], ids)
        for kind in (KINDS_ORG if row["dt"] == "org_chart" else KINDS_ACADEMIC):
            if kind == "dart_corp_code" and row["segment"] != "kr_listed":
                continue  # only Korean listed companies file with DART
            value = ids.get(kind)
            result, detail = check_identifier(kind, value, base, fetch=fetch, dart_key=dart_key,
                                              aliases=aliases, others=ids)
            conn.execute(
                "INSERT INTO identifier_check (probe_unit_id, kind, value, result, detail, checked_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (row["id"], kind, value, result, detail, now.isoformat(timespec="seconds")))
            out.append((row["slug"], kind, value or "", result, detail))
    return out


def known_answers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """Latest check per (unit, kind) that passed — the answers the known-answer benchmark may use."""
    return conn.execute(
        """SELECT c.probe_unit_id, c.kind, c.value FROM identifier_check c
           WHERE c.result IN ('ok','format_ok') AND c.id = (SELECT max(id) FROM identifier_check x
             WHERE x.probe_unit_id = c.probe_unit_id AND x.kind = c.kind)""").fetchall()
