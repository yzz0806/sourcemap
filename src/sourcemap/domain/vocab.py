"""Enumerations of the domain vocabulary (docs/domain.md §2, §5, §6, §9)."""

from enum import IntEnum, StrEnum


class Tier(IntEnum):
    """How much a source is trusted before measuring (docs/domain.md §5). Lower is stronger."""

    OFFICIAL = 1
    FIRST_PARTY = 2
    RESEARCHED = 3
    AGGREGATE = 4


class Subtype(StrEnum):
    OFFICIAL_FILING = "official_filing"
    FIRST_PARTY = "first_party"
    RESEARCHED = "researched"
    CROWD_EDITED = "crowd_edited"
    BIBLIOGRAPHIC = "bibliographic"
    PROFILE_AGGREGATE = "profile_aggregate"
    INFERRED = "inferred"


class Verdict(StrEnum):
    CORRECT = "correct"
    WRONG = "wrong"
    STALE = "stale"
    UNVERIFIABLE = "unverifiable"

    @property
    def decisive(self) -> bool:
        """Only correct and wrong enter accuracy (R8)."""
        return self in (Verdict.CORRECT, Verdict.WRONG)


class Method(StrEnum):
    """Verification methods. `strength` orders them: reference > lookup > agreement (R7)."""

    REFERENCE = "reference"
    LOOKUP = "lookup"
    AGREEMENT = "agreement"

    @property
    def strength(self) -> int:
        return {Method.REFERENCE: 3, Method.LOOKUP: 2, Method.AGREEMENT: 1}[self]


class CoverageState(StrEnum):
    MEASURED = "measured"
    NOT_PROBED = "not_probed"
    FAILED = "failed"


class AccuracyState(StrEnum):
    MEASURED = "measured"
    NOT_ENOUGH_DATA = "not_enough_data"
    UNMEASURED = "unmeasured"


class HealthState(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    BROKEN = "broken"
    SHAPE_CHANGED = "shape_changed"
    CHANGED = "changed"


class ValueKind(StrEnum):
    BOOL = "bool"
    TEXT = "text"
    ENTITY = "entity"
    URL = "url"
    EMAIL = "email"


class CompareMode(StrEnum):
    EXACT = "exact"
    NORMALISED = "normalised"
    JUDGE = "judge"


class RunKind(StrEnum):
    SETUP = "setup"
    MAINTENANCE = "maintenance"
    DISCOVERY = "discovery"
    BENCHMARK = "benchmark"


class RunMode(StrEnum):
    TEST = "test"
    REAL = "real"
