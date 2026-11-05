// The animation clock must produce the same number of ticks per second at any frame rate.
import { FixedStepClock } from "/tank/engine/clock.js";
import { assert, test } from "./check.js";

const TICK = 1 / 60;

function ticksOver(seconds, frameInterval) {
  const clock = new FixedStepClock(TICK);
  const frames = Math.round(seconds / frameInterval);
  let ticks = 0;
  for (let i = 0; i < frames; i++) {
    ticks += clock.advance(frameInterval);
  }
  return ticks;
}

test("tick count is independent of frame rate", () => {
  const at60 = ticksOver(10.0, 1 / 60);
  const at30 = ticksOver(10.0, 1 / 30);
  const at144 = ticksOver(10.0, 1 / 144);
  assert(Math.abs(at60 - 600) <= 1, `${at60} ticks at 60 fps`);
  assert(Math.abs(at30 - at60) <= 1, `${at30} ticks at 30 fps`);
  assert(Math.abs(at144 - at60) <= 1, `${at144} ticks at 144 fps`);
});

test("no drift from fractional frames: leftover time carries over", () => {
  const clock = new FixedStepClock(TICK);
  assert(clock.advance(TICK * 1.5) === 1);
  assert(clock.advance(TICK * 0.5) === 1);
});

test("a long stall (a tab in the background) is capped", () => {
  const clock = new FixedStepClock(TICK, 0.25);
  assert(clock.advance(5.0) === 15);
  assert(clock.advance(0.0) === 0, "the excess stall time is discarded, not replayed later");
});
