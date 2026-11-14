"""measure.drift (ADR 0012): alert only when intervals stop overlapping."""

from sourcemap.domain.model import Interval
from sourcemap.measure.drift import drift_alert


def test_overlapping_intervals_no_alert():
    assert not drift_alert(Interval(0.6, 0.9), Interval(0.5, 0.7))


def test_non_overlapping_intervals_alert():
    assert drift_alert(Interval(0.8, 0.95), Interval(0.4, 0.7))


def test_touching_intervals_overlap():
    assert not drift_alert(Interval(0.5, 0.7), Interval(0.7, 0.9))


def test_missing_interval_no_alert():
    assert not drift_alert(None, Interval(0.1, 0.2))
    assert not drift_alert(Interval(0.1, 0.2), None)
