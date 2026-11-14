"""R4 (lineage) and R7 (strongest method wins) — measure.verdicts."""

from datetime import datetime, timedelta

from sourcemap.domain.model import Claim, Source, Verification
from sourcemap.domain.vocab import Method, Subtype, Tier, Verdict
from sourcemap.measure.verdicts import (
    agreement_verdict,
    allowed_verifier,
    current_verdict,
    lookup_verdict,
    reference_verdict,
)

T0 = datetime(2026, 11, 14)
THEORG = Source(1, "theorg", Tier.RESEARCHED, Subtype.CROWD_EDITED, "theorg")
LINKEDIN = Source(2, "linkedin_apify", Tier.AGGREGATE, Subtype.PROFILE_AGGREGATE, "linkedin")
ZOOMINFO = Source(3, "zoominfo", Tier.AGGREGATE, Subtype.PROFILE_AGGREGATE, "linkedin")
APOLLO = Source(4, "apollo", Tier.AGGREGATE, Subtype.INFERRED, "linkedin")
GONG_PAGE = Source(5, "company:gong.io", Tier.FIRST_PARTY, Subtype.FIRST_PARTY, "company:gong.io")
OPENALEX = Source(6, "openalex", Tier.RESEARCHED, Subtype.BIBLIOGRAPHIC, "openalex",
                  (("profile_link", "orcid"),))
ORCID = Source(7, "orcid", Tier.RESEARCHED, Subtype.BIBLIOGRAPHIC, "orcid")


def claim(cid, source, value, entity=10, ct="title"):
    return Claim(cid, source.id, 100, ct, entity, value, value.lower())


# --- R4: lineage -------------------------------------------------------------------------------

def test_linkedin_can_check_a_theorg_title():
    assert allowed_verifier(THEORG, LINKEDIN, "title")


def test_linkedin_cannot_check_a_zoominfo_title_same_lineage():
    assert not allowed_verifier(ZOOMINFO, LINKEDIN, "title")


def test_a_source_never_checks_itself():
    assert not allowed_verifier(THEORG, THEORG, "title")


def test_lineage_per_claim_type_openalex_orcid():
    """ADR 0005: independent for affiliation, shared for profile_link."""
    assert allowed_verifier(OPENALEX, ORCID, "affiliation")
    assert not allowed_verifier(OPENALEX, ORCID, "profile_link")


def test_lookup_in_same_lineage_is_refused():
    assert lookup_verdict(claim(1, ZOOMINFO, "VP Sales"), ZOOMINFO, LINKEDIN, Verdict.CORRECT, T0) is None


def test_agreement_between_copies_counts_as_nothing():
    c = claim(1, ZOOMINFO, "VP Sales")
    others = [(claim(2, APOLLO, "VP Sales"), APOLLO), (claim(3, LINKEDIN, "VP Sales"), LINKEDIN)]
    assert agreement_verdict(c, ZOOMINFO, others, T0) is None


def test_agreement_across_lineages_is_half_weight():
    c = claim(1, THEORG, "VP Sales")
    v = agreement_verdict(c, THEORG, [(claim(2, GONG_PAGE, "VP Sales"), GONG_PAGE)], T0)
    assert v.verdict is Verdict.CORRECT and v.weight == 0.5


def test_agreement_on_an_inferred_source_weighs_zero():
    c = claim(1, APOLLO, "VP Sales")
    v = agreement_verdict(c, APOLLO, [(claim(2, THEORG, "VP Sales"), THEORG)], T0)
    assert v.weight == 0.0


def test_disagreement_is_not_a_wrong_verdict():
    c = claim(1, THEORG, "VP Sales")
    assert agreement_verdict(c, THEORG, [(claim(2, GONG_PAGE, "CFO"), GONG_PAGE)], T0) is None


def test_agreement_needs_the_same_entity():
    c = claim(1, THEORG, "VP Sales", entity=10)
    other = claim(2, GONG_PAGE, "VP Sales", entity=11)
    assert agreement_verdict(c, THEORG, [(other, GONG_PAGE)], T0) is None


def test_reference_undecided_comparison_gives_no_verdict():
    assert reference_verdict(claim(1, THEORG, "VP Sales"), THEORG, GONG_PAGE, None, T0) is None


# --- R7: one verdict per claim, strongest wins ------------------------------------------------

def v(method, verdict, days=0, expires=None):
    return Verification(1, method, verdict, T0 + timedelta(days=days), expires_at=expires)


def test_lookup_wrong_beats_agreement_correct():
    cur = current_verdict([v(Method.AGREEMENT, Verdict.CORRECT), v(Method.LOOKUP, Verdict.WRONG)], T0)
    assert cur.verdict is Verdict.WRONG


def test_reference_beats_lookup():
    cur = current_verdict([v(Method.LOOKUP, Verdict.WRONG), v(Method.REFERENCE, Verdict.CORRECT)], T0)
    assert cur.method is Method.REFERENCE


def test_same_method_newest_wins():
    cur = current_verdict([v(Method.LOOKUP, Verdict.CORRECT, 0), v(Method.LOOKUP, Verdict.STALE, 5)], T0)
    assert cur.verdict is Verdict.STALE


def test_expired_verdicts_do_not_count():
    old = v(Method.REFERENCE, Verdict.CORRECT, expires=T0 - timedelta(days=1))
    fresh = v(Method.AGREEMENT, Verdict.CORRECT)
    assert current_verdict([old, fresh], T0).method is Method.AGREEMENT
    assert current_verdict([old], T0) is None
