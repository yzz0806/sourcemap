"""Identifier checks with a fake fetcher — pipeline.idcheck (stage 2 check 3)."""

import pytest

from cases.idcheck_cases import IDCHECK_CASES
from sourcemap.sandbox.kit import BlockedByRobots, RawResponse
from sourcemap.pipeline.idcheck import check_identifier


class FakeFetch:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def __call__(self, url, **kw):
        self.calls.append(url)
        if self.responses.get("robots") == "blocked":
            raise BlockedByRobots(url)
        for key, (status, body) in self.responses.items():
            if key in url:
                return RawResponse(url=url, status=status, headers={}, body=body.encode())
        return RawResponse(url=url, status=404, headers={}, body=b"")


@pytest.mark.parametrize("case", IDCHECK_CASES, ids=lambda c: c[0])
def test_identifier_check(case):
    name, kind, value, unit_name, responses, expected = case
    dart_key = None if "without a key" in name else "test-key"
    fetch = FakeFetch(responses)
    result, detail = check_identifier(kind, value, unit_name, fetch=fetch, dart_key=dart_key,
                                      aliases=("Korea Advanced Institute of Science and Technology", "삼성전자"),
                                      others={"ror": "05apxxy63"})
    assert result == expected, detail
    if dart_key:
        assert all(dart_key not in d for d in [detail])  # the key never appears in stored details


def test_linkedin_is_never_fetched():
    fetch = FakeFetch({})
    check_identifier("linkedin", "https://www.linkedin.com/company/airtable/", "Airtable", fetch=fetch)
    assert fetch.calls == []


def test_dart_is_checked_only_for_korean_listed_units(tmp_path):
    from datetime import datetime
    from pathlib import Path

    from sourcemap.domain.specs import ALL_SPECS
    from sourcemap.pipeline.idcheck import run_checks
    from sourcemap.store.db import connect, migrate
    from sourcemap.store.seed import load_seed_files, seed

    root = Path(__file__).resolve().parents[2]
    conn = connect(tmp_path / "db.sqlite")
    migrate(conn)
    seed(conn, ALL_SPECS, load_seed_files(root / "seeds", units_file=root / "tests/fixtures/units_small.json"))
    rows = run_checks(conn, FakeFetch({}), now=datetime(2026, 11, 14))
    dart_units = {slug for slug, kind, *_ in rows if kind == "dart_corp_code"}
    assert dart_units == {"samsung-electronics"}
