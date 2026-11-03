"""Fixed-step animation clock: sprites advance in equal ticks however fast frames are drawn."""


class FixedStepClock:
    def __init__(self, tick_seconds: float, max_pending: float = 0.25):
        """
        :param tick_seconds: Simulated time per animation tick
        :param max_pending: Cap on accumulated real time, so a stall does not trigger a burst of catch-up ticks
        """
        self._tick = tick_seconds
        self._max_pending = max_pending
        self._pending = 0.0

    def advance(self, elapsed_seconds: float) -> int:
        """
        Account for real time that has passed and return how many ticks to run
        :param elapsed_seconds: Real time since the previous call
        :return: Number of whole ticks now due
        """
        self._pending = min(self._pending + elapsed_seconds, self._max_pending)
        ticks = int(self._pending / self._tick)
        self._pending -= ticks * self._tick
        return ticks
