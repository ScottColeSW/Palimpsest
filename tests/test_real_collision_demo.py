from __future__ import annotations

from palimpsest.real_collision_demo import RealCollisionDemo


def test_advances_through_both_real_pairs():
    demo = RealCollisionDemo()
    first = demo.advance()
    assert first.step == 1
    assert first.done is False
    assert first.domain == "fit"

    second = demo.advance()
    assert second.step == 2
    assert second.done is True
    assert second.domain == "blame"


def test_returns_none_once_exhausted():
    demo = RealCollisionDemo()
    demo.advance()
    demo.advance()
    assert demo.advance() is None


def test_both_real_pairs_are_genuinely_flagged_as_collisions():
    """The actual claim this page exists to make: real quoted text,
    run through the real consult() logic, both land on COLLIDES --
    not asserted, computed."""
    demo = RealCollisionDemo()
    first = demo.advance()
    second = demo.advance()
    assert first.relation == "collides"
    assert second.relation == "collides"


def test_state_reports_progress():
    demo = RealCollisionDemo()
    assert demo.state() == {"step": 0, "total": 2}
    demo.advance()
    assert demo.state() == {"step": 1, "total": 2}
