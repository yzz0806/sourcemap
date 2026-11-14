"""measure.monitor (ADR 0016): news hits reorder re-checks, never decide verdicts."""

from sourcemap.measure.monitor import MonitorMatch, NewsHit, TrackedEntity, match_hits, prioritise

GONG, AIRTABLE = 1, 2
JANE = TrackedEntity(10, GONG, ("Jane Smith", "J. Smith"))
JOHN = TrackedEntity(11, GONG, ("John Doe",))
PARK = TrackedEntity(12, 3, ("박형관", "Hyung-Kwan Park"))
JANE_AT_AIRTABLE = TrackedEntity(13, AIRTABLE, ("Jane Smith",))


def test_full_name_in_headline_matches():
    hits = [NewsHit(1, GONG, "Gong's VP Sales Jane Smith steps down")]
    assert match_hits(hits, [JANE, JOHN]) == [MonitorMatch(1, 10, "Jane Smith")]


def test_surname_alone_does_not_match():
    hits = [NewsHit(1, GONG, "Smith joins Gong board")]
    assert match_hits(hits, [JANE]) == []


def test_only_entities_of_the_same_company_match():
    hits = [NewsHit(1, GONG, "Jane Smith leaves Gong")]
    assert [m.entity_id for m in match_hits(hits, [JANE, JANE_AT_AIRTABLE])] == [10]


def test_name_in_snippet_with_accents_and_case_matches():
    hits = [NewsHit(2, GONG, "Leadership change", "JANE SMÍTH has been appointed CRO")]
    assert len(match_hits(hits, [JANE])) == 1


def test_hangul_name_matches():
    hits = [NewsHit(3, 3, "삼성전자 박형관 부사장 승진")]
    assert [m.entity_id for m in match_hits(hits, [PARK])] == [12]


def test_matched_title_and_employment_claims_go_first():
    queue = [100, 101, 102]
    claims = {10: [(200, "title"), (201, "employment"), (202, "reports_to")]}
    out = prioritise(queue, [MonitorMatch(1, 10, "Jane Smith")], claims)
    assert out == [200, 201, 100, 101, 102]


def test_matched_claims_already_in_queue_are_not_duplicated():
    out = prioritise([5, 200, 6], [MonitorMatch(1, 10, "x"), MonitorMatch(2, 10, "x")], {10: [(200, "title")]})
    assert out == [200, 5, 6]


def test_share_cap_limits_promoted_claims():
    claims = {10: [(200, "title"), (201, "employment")]}
    out = prioritise([1], [MonitorMatch(1, 10, "x")], claims, share_cap=1)
    assert out == [200, 1]
