"""measure.health against tests/cases/health_cases.py (ADR 0012)."""

import pytest

from cases.health_cases import HEALTH_CASES
from sourcemap.measure.health import RunStats, source_health


def _stats(t):
    return None if t is None else RunStats(*t)


@pytest.mark.parametrize("name,prev,this,expected", HEALTH_CASES, ids=[c[0] for c in HEALTH_CASES])
def test_health_case(name, prev, this, expected):
    assert source_health(_stats(prev), _stats(this)) is expected
