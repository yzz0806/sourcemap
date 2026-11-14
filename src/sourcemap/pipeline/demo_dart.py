"""DART reference for the multi-company demo: the 2025 annual report's executive tables.

The `exctvSttus` API returns only registered directors, so the full executive list (미등기임원 too)
is parsed from the report document itself, which is stored unchanged in the raw store (R10).
"""

import io
import json
import re
import zipfile
from pathlib import Path

from sourcemap.sandbox.kit import Kit
from sourcemap.store.rawstore import RawStore

API = "https://opendart.fss.or.kr/api"


def parse_exec_rows(xml: str) -> list[dict]:
    """Executive rows: name | sex | birth (YYYY.MM) | rank | full-time | responsibility | career …"""
    rows = []
    for tr in re.findall(r"<TR[^>]*>(.*?)</TR>", xml, re.S | re.I):
        cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<T[DE][^>]*>(.*?)</T[DE]>", tr, re.S | re.I)]
        if len(cells) >= 7 and cells[1] in ("남", "여") and re.match(r"\d{4}\.\d{2}$", cells[2]):
            rows.append({"name": cells[0], "sex": cells[1], "birth_ym": cells[2], "title": cells[3],
                         "fulltime": cells[4], "responsibility": cells[5], "career": cells[6]})
    return rows


def fetch_reference(kit: Kit, key: str, corp_code: str, raw: RawStore, year: str = "2025") -> dict:
    """Find the annual report, store its document raw, return the parsed executives + provenance."""
    r = kit.get(f"{API}/exctvSttus.json", params={"crtfc_key": key, "corp_code": corp_code,
                                                  "bsns_year": year, "reprt_code": "11011"})
    body = json.loads(r.text())
    if body.get("status") != "000":
        raise RuntimeError(f"DART {corp_code}: status {body.get('status')} {body.get('message')}")
    rcept = body["list"][0]["rcept_no"]
    doc = kit.get(f"{API}/document.xml", params={"crtfc_key": key, "rcept_no": rcept})
    sha = raw.put(doc.body)
    z = zipfile.ZipFile(io.BytesIO(doc.body))
    rows = []
    for name in z.namelist():
        rows += parse_exec_rows(z.read(name).decode("utf-8", errors="replace"))
    seen, uniq = set(), []
    for r_ in rows:  # the same table can appear twice in a filing
        k = (r_["name"], r_["birth_ym"], r_["title"])
        if k not in seen:
            seen.add(k)
            uniq.append(r_)
    return {"corp_code": corp_code, "rcept_no": rcept, "sha256": sha, "year": year,
            "viewer_url": f"https://dart.fss.or.kr/dsaf001/main.do?rcpNo={rcept}", "execs": uniq}
