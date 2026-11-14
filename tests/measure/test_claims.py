"""Splitting records into claims and claim fingerprints — measure.claims."""

from sourcemap.domain.model import Record
from sourcemap.domain.specs import ACADEMIC_IDENTITY, ORG_CHART
from sourcemap.measure.claims import extract_claims, fingerprint

AIRTABLE = Record(1, 1, 100, payload={"people": [
    {"ref": "howie", "name": "Howie Liu", "title": "CEO"},
    {"ref": "jane", "name": "Jane Smith", "title": "VP Sales", "manager_ref": "howie"},
    {"ref": "bob", "name": "Bob Lee", "title": "  ", "manager_ref": "nobody-here"},
    {"ref": "x", "name": "", "title": "Ghost"},
]})


def drafts_by(record, spec):
    return {(d.person_ref, d.claim_type): d for d in extract_claims(spec, record)}


def test_org_chart_record_splits_into_claims():
    d = drafts_by(AIRTABLE, ORG_CHART)
    assert d[("howie", "employment")].value is True
    assert d[("howie", "title")].value_norm == "ceo"
    assert d[("jane", "reports_to")].value == "howie"
    assert ("howie", "reports_to") not in d


def test_empty_values_and_unresolvable_managers_are_skipped():
    d = drafts_by(AIRTABLE, ORG_CHART)
    assert ("bob", "employment") in d
    assert ("bob", "title") not in d          # blank title
    assert ("bob", "reports_to") not in d     # manager not in this record
    assert not any(ref == "x" for ref, _ in d)  # person without a name


def test_invalid_record_yields_nothing():
    bad = Record(2, 1, 100, valid=False, payload=AIRTABLE.payload)
    assert extract_claims(ORG_CHART, bad) == []


def test_academic_record():
    rec = Record(3, 6, 200, payload={"people": [
        {"ref": "a1", "name": "Ada Kim", "role": "PhD student", "email": "Ada@Purdue.edu",
         "profile_link": "https://orcid.org/0000-0002-1825-0097/"},
    ]})
    d = drafts_by(rec, ACADEMIC_IDENTITY)
    assert d[("a1", "exists")].value is True
    assert d[("a1", "email")].value_norm == "ada@purdue.edu"
    assert d[("a1", "profile_link")].value_norm == "orcid.org/0000-0002-1825-0097"
    assert ("a1", "affiliation") not in d


def test_fingerprint_is_stable_and_sensitive():
    a = fingerprint(1, 100, 7, "title", "ceo")
    assert a == fingerprint(1, 100, 7, "title", "ceo")
    assert a != fingerprint(1, 100, 8, "title", "ceo")
    assert a != fingerprint(1, 100, 7, "title", "cfo")
    assert len(a) == 40
