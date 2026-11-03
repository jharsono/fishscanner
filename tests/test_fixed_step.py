"""The animation clock must produce the same number of ticks per second at any frame rate."""

from engine.clock import FixedStepClock

TICK = 1 / 60


def ticks_over(seconds: float, frame_interval: float) -> int:
    clock = FixedStepClock(TICK)
    frames = round(seconds / frame_interval)
    return sum(clock.advance(frame_interval) for _ in range(frames))


def test_tick_count_is_independent_of_frame_rate():
    at_60 = ticks_over(10.0, 1 / 60)
    at_30 = ticks_over(10.0, 1 / 30)
    at_144 = ticks_over(10.0, 1 / 144)
    assert abs(at_60 - 600) <= 1
    assert abs(at_30 - at_60) <= 1
    assert abs(at_144 - at_60) <= 1


def test_no_drift_from_fractional_frames():
    """Leftover time carries over instead of being discarded each frame."""
    clock = FixedStepClock(TICK)
    assert clock.advance(TICK * 1.5) == 1
    assert clock.advance(TICK * 0.5) == 1


def test_long_stall_is_capped():
    """A stall (window drag, sleep) does not trigger hundreds of catch-up ticks."""
    clock = FixedStepClock(TICK, max_pending=0.25)
    assert clock.advance(5.0) == 15
    assert clock.advance(0.0) == 0  # The excess stall time is discarded, not replayed later
