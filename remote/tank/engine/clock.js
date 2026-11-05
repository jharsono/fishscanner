// Fixed-step animation clock: sprites advance in equal ticks however fast frames are drawn.

export class FixedStepClock {
  /**
   * @param {number} tickSeconds Simulated time per animation tick
   * @param {number} maxPending Cap on accumulated real time, so a stall does not trigger a burst of catch-up ticks
   */
  constructor(tickSeconds, maxPending = 0.25) {
    this._tick = tickSeconds;
    this._maxPending = maxPending;
    this._pending = 0.0;
  }

  /**
   * Account for real time that has passed and return how many ticks to run
   * @param {number} elapsedSeconds Real time since the previous call
   * @returns {number} Number of whole ticks now due
   */
  advance(elapsedSeconds) {
    this._pending = Math.min(this._pending + elapsedSeconds, this._maxPending);
    const ticks = Math.floor(this._pending / this._tick);
    this._pending -= ticks * this._tick;
    return ticks;
  }
}
