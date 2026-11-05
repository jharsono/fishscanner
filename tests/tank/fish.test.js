// Sprite animation logic, run without a WebGL context (meshes are created lazily on first render).
// Ported from tests/test_fish.py (tag desktop-final). Those tests start from numpy's seed 0, whose
// first fish enters from the left and so faces right, and several of them rely on that (a turn at
// a wall ends at rotate 180, a level entry has no pitch); each fishTest here starts from a seed
// whose fish does the same.
import { Renderer } from "/tank/engine/renderer.js";
import { randint, seed } from "/tank/engine/random.js";
import { DrawingBubble } from "/tank/ocean/drawingbubble.js";
import {
  copysign,
  DrawingFish,
  distanceCycle,
  EFFORT_LEVELS,
  ENTRY_LEVELLING,
  ENTRY_SPEED,
  FAR_SCALE,
  FAR_SPEED,
  FAR_TINT,
  FAR_Z,
  HEAD_TURN,
  MAX_PITCH,
  mod,
  PITCH_DEADBAND,
  PITCH_FULL_AT,
  pitchForClimb,
  preventDepthCrossings,
  TURN_RATE,
  WANDER,
} from "/tank/ocean/drawingfish.js";
import { assert, assertAllClose, assertClose, isClose, test } from "./check.js";

const ENTRY_SIDES = ["left", "right", "top", "bottom"];

function fishTest(name, body) {
  test(name, () => {
    seedEntering("left");
    body();
  });
}

/** Seed so the next fish enters from a side: the first number a fish draws is its entry side */
function seedEntering(side) {
  for (let candidate = 0; ; candidate++) {
    seed(candidate);
    if (randint(4) === ENTRY_SIDES.indexOf(side)) {
      seed(candidate);
      return;
    }
  }
}

/** A fish entering from a side, checked by the way it is heading */
function fishEntering(side) {
  seedEntering(side);
  const fish = new DrawingFish(null);
  const [vx, vy] = fish.vector;
  const heading = { left: vx > 0 && vy === 0, right: vx < 0 && vy === 0, top: vy > 0, bottom: vy < 0 }[side];
  assert(heading, `a fish entering from the ${side} heads [${vx}, ${vy}]`);
  return fish;
}

function startSwimming(fish) {
  animate(fish, fish._initAnimationStep + 1); // Read once: the entry counts it down as it runs
}

function animate(fish, ticks) {
  for (let i = 0; i < ticks; i++) {
    fish.animation();
  }
}

function step2(after, before) {
  return Math.hypot(after[0] - before[0], after[1] - before[1]);
}

function headingOf(fish) {
  return Math.atan2(fish.vector[1], fish.vector[0]);
}

function speedOf(fish) {
  return Math.hypot(fish.vector[0], fish.vector[1]);
}

/** Difference between two angles in radians, wrapped to [0, pi] */
function angleStep(a, b) {
  return Math.abs(mod(b - a + Math.PI, 2 * Math.PI) - Math.PI);
}

function holdEffort(fish, effort) {
  fish.effort = fish._effortTarget = effort;
  fish._effortTicksLeft = 10 ** 6;
}

/** A fish already past a border and still heading out, as a long entry animation can leave it */
function swimmingFishBeyond(position, vector) {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 10 ** 6; // Keep full speed for a clear count
  holdEffort(fish, 1.0);
  fish.position = [...position];
  fish.vector = [...vector];
  fish._cruiseSpeed = Math.hypot(vector[0], vector[1]); // This is its pace; nothing eases it away
  return fish;
}

function swimmingFishAt(x, y) {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  holdEffort(fish, 1.0);
  fish._depthPeriod = 600;
  fish.position = [x, y, 0.0];
  fish.vector = [0.0, 0.0, 0.0]; // Hold still so the test is about depth, not motion
  fish._cruiseSpeed = 0.0;
  // Level too: a vertical entry can leave a trace of pitch, which widens the fish's box (the
  // Python tests' fish happened to enter level)
  fish.rotate[2] = 0.0;
  return fish;
}

function countDirectionChanges(fish, axis, ticks) {
  let changes = 0;
  let last = Math.sign(fish.vector[axis]);
  for (let i = 0; i < ticks; i++) {
    fish.animation();
    if (Math.sign(fish.vector[axis]) !== last) {
      changes += 1;
      last = Math.sign(fish.vector[axis]);
    }
  }
  return changes;
}

function facesItsHeading(fish) {
  return (fish.vector[0] >= 0) === (fish._baseScale[0] >= 0) ? 0 : 180;
}

test("mod wraps like Python's %: the result takes the divisor's sign", () => {
  assert(mod(-90, 360) === 270 && mod(370, 360) === 10 && mod(0, 360) === 0);
  assertClose(mod(-0.5 * Math.PI, 2 * Math.PI), 1.5 * Math.PI);
});

test("copysign gives the magnitude the sign of the second number, minus zero included", () => {
  assert(copysign(2, -3) === -2 && copysign(-2, 3) === 2 && copysign(1, -0) === -1 && copysign(1, 0) === 1);
});

fishTest("a fish can be built without a WebGL context", () => {
  const fish = new DrawingFish(null);
  assert(fish.isAlive && fish.isTransparent);
});

fishTest("all off-screen bubbles are removed in one step", () => {
  const fish = new DrawingFish(null);
  fish._bubbleRandomFrequency = 10 ** 9; // Never spawn new bubbles during the test
  for (let i = 0; i < 6; i++) {
    fish._bubbles.push(new DrawingBubble(null, { startX: 0.0, startY: -2.0 })); // Already above the top edge
  }
  fish.animation();
  assert(fish.getChildSprites().length === 0);
});

fishTest("a fish that goes away dies once off screen", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish.goAway();
  for (let i = 0; i < 5000 && fish.isAlive; i++) {
    fish.animation();
  }
  assert(!fish.isAlive);
});

fishTest("the renderer draws bubbles as children of fish", () => {
  const fish = new DrawingFish(null);
  const bubble = new DrawingBubble(null, { startX: 0.0, startY: 0.0 });
  fish._bubbles.push(bubble);
  const sprites = Renderer.allSprites([fish]);
  assert(sprites.length === 2 && sprites[0] === fish && sprites[1] === bubble);
  assert(bubble.isTransparent);
});

fishTest("the distance cycle is near at both ends and far in the middle", () => {
  assert(distanceCycle(0, 600) === 0.0);
  assertClose(distanceCycle(300, 600), 1.0);
  assertClose(distanceCycle(600, 600), 0.0);
});

fishTest("a fish shrinks into the distance and grows back", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 600;
  const base = Math.abs(fish.scale[0]);
  const sizes = [];
  for (let i = 0; i < 600; i++) {
    fish.animation();
    sizes.push(Math.abs(fish.scale[0]));
  }
  assertClose(Math.min(...sizes), base * FAR_SCALE, { rtol: 0.01 });
  assertClose(sizes[sizes.length - 1], base, { rtol: 0.01 }); // Back to its original size after one full cycle
  assert(Math.max(...sizes) <= base * 1.001, "never larger than the original");
});

fishTest("facing direction survives the distance cycle", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 200;
  const facing = Math.sign(fish.scale[0]);
  for (let i = 0; i < 200; i++) {
    fish.animation();
    assert(Math.sign(fish.scale[0]) === facing);
  }
});

fishTest("a far fish moves slower, dims and sits behind", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 600;
  // Effort changes the pace too, so hold it: the Python test passed only because numpy's seed 0
  // happens not to change gear before tick 300
  holdEffort(fish, 1.0);
  let before = [...fish.position];
  fish.animation();
  const nearStep = step2(fish.position, before);
  assert(isClose(fish.position[2], 0.0, { atol: 1e-3 }));
  assertAllClose(fish.color, [1, 1, 1], { atol: 1e-3 });
  animate(fish, 298);
  before = [...fish.position];
  fish.animation(); // Tick 300 of 600: the far point
  const farStep = step2(fish.position, before);
  assertClose(farStep / nearStep, FAR_SPEED, { rtol: 0.02 });
  assertClose(fish.position[2], FAR_Z, { rtol: 0.01 });
  assert(fish.color[0] < 1.0);
});

fishTest("a left-facing fish keeps facing left through the cycle", () => {
  const fish = fishEntering("right"); // Enters from the right, so it faces left
  assert(fish._baseScale[0] < 0);
  startSwimming(fish);
  fish._depthPeriod = 300;
  for (let i = 0; i < 300; i++) {
    fish.animation();
    assert(fish.scale[0] < 0);
  }
});

fishTest("no jump between entry and swimming", () => {
  const fish = new DrawingFish(null);
  animate(fish, fish._initAnimationStep - 1);
  const scale = [...fish.scale];
  const color = [...fish.color];
  const z = fish.position[2];
  fish.animation(); // Last entry tick switches to swimming
  fish.animation(); // First swimming tick
  assertAllClose(fish.scale, scale, { atol: 1e-4 });
  assertAllClose(fish.color, color, { atol: 1e-4 });
  assertClose(fish.position[2], z, { atol: 1e-4 });
});

fishTest("far point values are exact", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 600;
  fish._depthTick = 0;
  animate(fish, 300);
  assertAllClose(
    fish.scale.map(Math.abs),
    fish._baseScale.map((value) => Math.abs(value) * FAR_SCALE),
  );
  assertAllClose(fish.color, [FAR_TINT, FAR_TINT, FAR_TINT]);
  assertClose(fish.position[2], FAR_Z);
});

fishTest("bubbles inherit the parent fish's distance", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 600;
  fish._depthTick = 0;
  animate(fish, 300);
  fish._bubbleRandomFrequency = 1; // Spawn on the next step
  fish.animation();
  const children = fish.getChildSprites();
  const bubble = children[children.length - 1];
  assertClose(bubble.position[2], FAR_Z);
  assertAllClose(bubble.color, [FAR_TINT, FAR_TINT, FAR_TINT]);
  assert(bubble.scale[0] <= 0.15 * FAR_SCALE + 1e-9, "bubble sizes are drawn up to 0.15, then shrunk with the fish");
});

fishTest("a fish leaving from the far point exits at full pace", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 600;
  animate(fish, 300);
  fish.goAway();
  const before = [...fish.position];
  const pace = Math.abs(fish.vector[0]);
  fish.animation();
  assertClose(Math.abs(fish.position[0] - before[0]), pace * fish.effort);
});

for (const [position, vector, axis, where] of [
  [[2.0, 0.0, 0.0], [0.003, 0.0, 0.0], 0, "beyond the right border"],
  [[-2.0, 0.0, 0.0], [-0.003, 0.0, 0.0], 0, "beyond the left border"],
  [[0.0, 0.6, 0.0], [0.0, 0.002, 0.0], 1, "below the bottom bound"],
  [[0.0, -1.0, 0.0], [0.0, -0.002, 0.0], 1, "above the top bound"],
]) {
  fishTest(`a fish ${where} turns once and comes back`, () => {
    const fish = swimmingFishBeyond(position, vector);
    assert(countDirectionChanges(fish, axis, 600) === 1);
    assert(fish._left < fish.position[0] && fish.position[0] < fish._right);
    assert(fish._top < fish.position[1] && fish.position[1] < fish._bottom);
    assert(fish.rotate[1] === facesItsHeading(fish) && fish.rotationVector[1] === 0);
  });
}

fishTest("a fish beyond a corner turns once and comes back", () => {
  const fish = swimmingFishBeyond([2.0, 0.6, 0.0], [0.003, 0.002, 0.0]);
  assert(countDirectionChanges(fish, 0, 600) === 1, "one arc, not a bounce on each wall");
  assert(fish._left < fish.position[0] && fish.position[0] < fish._right);
  assert(fish._top < fish.position[1] && fish.position[1] < fish._bottom);
  assert(fish.rotate[1] === 180 && fish.rotationVector[1] === 0, "entered heading right, left heading left");
});

test("each fish has its own tempo", () => {
  const tempos = new Set();
  for (let candidate = 0; candidate < 5; candidate++) {
    seed(candidate);
    tempos.add(new DrawingFish(null).tempo.toFixed(4));
  }
  assert(tempos.size === 5);
});

fishTest("effort ebbs and flows within bounds", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  const efforts = [];
  for (let i = 0; i < 60 * 60; i++) {
    // A minute of swimming
    fish.animation();
    efforts.push(fish.effort);
  }
  const levels = Object.values(EFFORT_LEVELS);
  assert(Math.min(...levels) - 1e-6 <= Math.min(...efforts));
  assert(Math.max(...efforts) <= Math.max(...levels) + 1e-6);
  assert(Math.max(...efforts) - Math.min(...efforts) > 0.5, "effort never changed");
  const jumps = efforts.slice(1).map((effort, i) => Math.abs(effort - efforts[i]));
  assert(Math.max(...jumps) < 0.1, "transitions are eased, never a jump");
});

fishTest("speed and tail beat follow effort", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish._depthPeriod = 10 ** 6;
  holdEffort(fish, 0.5);
  let before = [...fish.position];
  let phaseBefore = fish._tailPhase;
  fish.animation();
  const slowStep = step2(fish.position, before);
  const slowBeat = fish._tailPhase - phaseBefore;
  holdEffort(fish, 2.0);
  before = [...fish.position];
  phaseBefore = fish._tailPhase;
  fish.animation();
  const fastStep = step2(fish.position, before);
  const fastBeat = fish._tailPhase - phaseBefore;
  assertClose(fastStep / slowStep, 4.0, { rtol: 0.01 });
  assert(fastBeat > slowBeat * 1.5);
  assert(fish.shaderParams[0] === fish._tailPhase);
  assert(fish.shaderParams[1] > 0);
});

fishTest("a fish told to leave bursts", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  fish.goAway();
  assert(fish._effortTarget === EFFORT_LEVELS.burst);
});

fishTest("effort always changes gear when re-picked", () => {
  const fish = new DrawingFish(null);
  startSwimming(fish);
  const seen = [];
  for (let i = 0; i < 60 * 120; i++) {
    const before = fish._effortTarget;
    fish.animation();
    if (fish._effortTarget !== before) {
      seen.push([before, fish._effortTarget]);
    }
  }
  assert(seen.length >= 10);
  assert(seen.every(([a, b]) => a !== b));
});

test("fish end up out of phase", () => {
  const phases = new Set();
  for (let candidate = 0; candidate < 4; candidate++) {
    seed(candidate);
    const fish = new DrawingFish(null);
    startSwimming(fish);
    animate(fish, 600);
    phases.add(mod(fish._tailPhase, 2 * Math.PI).toFixed(2));
  }
  assert(phases.size === 4);
});

fishTest("fish overlap is judged from their drawn extents", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(0.9, 0.0); // Fish are 1.0 wide: edges touch at 0.5 vs 0.4
  const c = swimmingFishAt(1.2, 0.0);
  assert(a.overlaps(b) && b.overlaps(a));
  assert(!a.overlaps(c));
});

fishTest("overlap uses the painted extent, not the whole canvas", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(0.7, 0.0);
  assert(a.overlaps(b), "full quads (1.0 wide) overlap");
  a.extent = [0.5, 1.0]; // Paint covers only the middle half of each canvas
  b.extent = [0.5, 1.0];
  assert(!a.overlaps(b));
});

fishTest("depth cycles continue but never cross while overlapping", () => {
  const a = swimmingFishAt(0.0, 0.0); // Near (tick 0), heading away
  const b = swimmingFishAt(0.3, 0.1);
  b._depthTick = 300; // Far point, heading back toward the front: the two would meet
  for (let i = 0; i < 300; i++) {
    preventDepthCrossings([a, b]);
    a.animation();
    b.animation();
    assert(a.position[2] >= b.position[2], "a stays in front for the whole overlap");
  }
  assert(0 < a._depthTick && a._depthTick <= 152 && 300 < b._depthTick, "both cycled to the meeting point, then held");
  b.position[0] = 2.0; // Now clear of each other
  const held = [a._depthTick, b._depthTick];
  for (let i = 0; i < 50; i++) {
    preventDepthCrossings([a, b]);
    a.animation();
    b.animation();
  }
  assert(a._depthTick === held[0] + 50 && b._depthTick === held[1] + 50, "both resume");
});

test("many fish keep cycling and never pass through each other", () => {
  // Six fish with real-sized painted extents (scans cover ~0.75 x 0.85 of their canvas)
  const fishes = [];
  for (let candidate = 0; candidate < 6; candidate++) {
    seed(candidate);
    const fish = new DrawingFish(null, { extent: [0.75, 0.85] });
    startSwimming(fish);
    fishes.push(fish);
  }
  const advanced = fishes.map(() => 0);
  let crossings = 0;
  for (let tick = 0; tick < 3600; tick++) {
    // One minute
    const beforeZ = fishes.map((fish) => fish.position[2]);
    const beforeTick = fishes.map((fish) => fish._depthTick);
    preventDepthCrossings(fishes);
    for (const fish of fishes) {
      fish.animation();
    }
    fishes.forEach((fish, i) => {
      advanced[i] += fish._depthTick > beforeTick[i] ? 1 : 0;
      for (let k = i + 1; k < 6; k++) {
        const swapped =
          Math.sign(beforeZ[i] - beforeZ[k]) * Math.sign(fish.position[2] - fishes[k].position[2]) < 0;
        if (fish.overlaps(fishes[k]) && swapped) {
          crossings += 1;
        }
      }
    });
  }
  assert(crossings === 0, `${crossings} crossings`);
  // Fish that travel together in arcs stay overlapped for long stretches, so a third of the
  // minute cycling on average, and never less than ten seconds for any fish, is the bar
  const mean = advanced.reduce((sum, value) => sum + value, 0) / advanced.length;
  assert(Math.min(...advanced) > 600 && mean > 1200, `fish spent too long held: ${advanced}`);
});

fishTest("the overlap look-ahead sees fish about to meet or grow into each other", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(1.2, 0.0); // Just clear: half widths sum to 1.0 with full-canvas extents
  assert(!a.overlaps(b) && !a.overlaps(b, { afterStep: true }));
  b.vector = [-0.3, 0.0, 0.0]; // Would step well into a next tick
  assert(!a.overlaps(b) && a.overlaps(b, { afterStep: true }));
  b.vector = [0.0, 0.0, 0.0];
  b._depthTick = 299; // At the far point, small; next step it starts growing back
  b._applyDistance(1.0);
  b.position[0] = 0.5 + Math.abs(b.scale[0]) / 2 + 1e-4; // Touching distance at the current, shrunken size
  assert(!a.overlaps(b));
  b._depthTick = 400; // Growing quickly on the way back
  assert(a.overlaps(b, { afterStep: true }));
});

fishTest("an equal-depth tie holds only one fish", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(0.2, 0.0); // Both at depth tick 0, z 0, overlapping
  for (let i = 0; i < 30; i++) {
    preventDepthCrossings([a, b]);
    a.animation();
    b.animation();
  }
  assert(a._depthTick !== b._depthTick && Math.min(a._depthTick, b._depthTick) > 0, "one waited a tick");
  // At equal depth the renderer draws the earlier sprite on top, so that one must stay on top
  assert(a.position[2] > b.position[2]);
});

fishTest("the look-ahead predicts the eased effort, not the current one", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(1.2, 0.0); // Just clear at full-canvas extents
  b.vector = [-0.05, 0.0, 0.0];
  b.effort = 0.0;
  b._effortTarget = 2.0; // The next move uses the eased effort, which is above zero
  assert(a.overlaps(b, { afterStep: true }) === b._nextEffort() * 0.05 > 0.2);
  b._effortTarget = 0.0;
  assert(!a.overlaps(b, { afterStep: true }));
});

fishTest("a turn at a wall is a smooth arc, not a bounce", () => {
  const fish = swimmingFishBeyond([1.2, -0.2, 0.0], [0.003, 0.0, 0.0]); // Inside the border, heading for it
  const speed = speedOf(fish);
  const headings = [headingOf(fish)];
  let xChanges = 0;
  for (let i = 0; i < 400; i++) {
    const before = Math.sign(fish.vector[0]);
    fish.animation();
    xChanges += Math.sign(fish.vector[0]) !== before ? 1 : 0;
    headings.push(headingOf(fish));
    assertClose(speedOf(fish), speed, { rtol: 1e-6 }); // Speed is kept, only direction turns
  }
  const steps = headings.slice(1).map((heading, i) => angleStep(headings[i], heading));
  assert(Math.max(...steps) <= TURN_RATE + 1e-9, "heading jumped instead of turning");
  assert(xChanges === 1);
  assert(fish.vector[0] < 0 && fish.position[0] < fish._right + 0.1);
  assert(fish.rotate[1] === 180 && fish.rotationVector[1] === 0);
});

fishTest("a fish faces the way it is heading after turning twice", () => {
  const fish = swimmingFishBeyond([1.2, -0.2, 0.0], [0.003, 0.0, 0.0]);
  animate(fish, 400);
  assert(fish.vector[0] < 0 && fish.rotate[1] === 180);
  fish.position[0] = -1.2; // Carry it to the other wall still heading left
  animate(fish, 400);
  assert(fish.vector[0] > 0 && fish.rotate[1] === 0);
});

for (const [wallX, vx] of [
  [1.2, 0.003],
  [-1.2, -0.003],
]) {
  fishTest(`a turn at the wall at x ${wallX} curves toward the middle of the tank`, () => {
    // Straight at a side wall, clear of the top and bottom margins, so only the tie-break decides
    const middle = -0.2;
    const low = swimmingFishBeyond([wallX, 0.05, 0.0], [vx, 0.0, 0.0]); // Below the middle (y grows downwards)
    const high = swimmingFishBeyond([wallX, -0.45, 0.0], [vx, 0.0, 0.0]); // Above the middle
    animate(low, 90);
    animate(high, 90);
    assert(low.position[1] < 0.05 && Math.abs(low.position[1] - middle) < Math.abs(0.05 - middle));
    assert(high.position[1] > -0.45 && Math.abs(high.position[1] - middle) < Math.abs(-0.45 - middle));
  });
}

fishTest("a bursting fish straight at the top turns before leaving the screen", () => {
  const fish = swimmingFishBeyond([0.0, -0.3, 0.0], [0.0, -0.003, 0.0]); // Straight up at full pace
  holdEffort(fish, 1.9);
  let lowestY = 0.0;
  for (let i = 0; i < 300; i++) {
    fish.animation();
    lowestY = Math.min(lowestY, fish.position[1]);
  }
  assert(lowestY > fish._top - 0.07 && fish.vector[1] > 0, "turned back down within a small overshoot");
});

fishTest("a fish told to leave from a vertical heading still leaves", () => {
  const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [0.0, -0.003, 0.0]); // Mid-turn, heading straight up
  fish.goAway();
  for (let i = 0; i < 1500 && fish.isAlive; i++) {
    fish.animation();
  }
  assert(!fish.isAlive, `still in the tank at ${fish.position.slice(0, 2)}`);
  assert(fish.rotate[1] === facesItsHeading(fish), "faced the way it left");
});

for (const [wallY, vy] of [
  [-0.55, -0.003],
  [0.15, 0.003],
]) {
  fishTest(`a turn at y ${wallY} curves toward the tank centre`, () => {
    const left = swimmingFishBeyond([-0.8, wallY, 0.0], [0.0, vy, 0.0]);
    const right = swimmingFishBeyond([0.8, wallY, 0.0], [0.0, vy, 0.0]);
    animate(left, 90);
    animate(right, 90);
    assert(left.position[0] > -0.8 && right.position[0] < 0.8, "each arcs toward x = 0");
  });
}

for (const side of ENTRY_SIDES) {
  fishTest(`an entry from the ${side} eases out to cruising speed with no jump into swimming`, () => {
    const fish = fishEntering(side);
    holdEffort(fish, 1.0);
    assertClose(speedOf(fish), ENTRY_SPEED);
    const speeds = [speedOf(fish)];
    let stageChangedAt = null;
    const ticks = fish._initAnimationStep + 60; // Read once: the entry counts it down as it runs
    for (let tick = 0; tick < ticks; tick++) {
      fish.animation();
      speeds.push(speedOf(fish));
      if (stageChangedAt === null && fish._animationStage === "swim") {
        stageChangedAt = tick;
      }
    }
    const ratios = speeds.slice(1).map((speed, i) => speed / speeds[i]);
    assert(Math.max(...ratios) <= 1.0 + 1e-9, "the fish sped up during its entry");
    assert(Math.min(...ratios) >= 0.9, "a speed jump: entry speed must ease out, never snap");
    assert(stageChangedAt !== null);
    assert(isClose(speeds[speeds.length - 1], fish._cruiseSpeed) && 0.002 <= fish._cruiseSpeed && fish._cruiseSpeed <= 0.003);
  });

  fishTest(`an entry from the ${side} changes heading gradually with no jump into swimming`, () => {
    const fish = fishEntering(side);
    holdEffort(fish, 1.0);
    const headings = [headingOf(fish)];
    const ticks = fish._initAnimationStep + 30; // Read once: the entry counts it down as it runs
    for (let i = 0; i < ticks; i++) {
      fish.animation();
      headings.push(headingOf(fish));
    }
    const steps = headings.slice(1).map((heading, i) => angleStep(headings[i], heading));
    assert(Math.max(...steps) <= Math.max(ENTRY_LEVELLING, TURN_RATE) + WANDER + 1e-9);
    assert(fish._animationStage === "swim");
  });
}

for (const side of ["top", "bottom"]) {
  fishTest(`a vertical entry from the ${side} arrives level and facing its way`, () => {
    const fish = fishEntering(side);
    assert(Math.abs(fish.vector[0]) > 0, "never dead vertical");
    holdEffort(fish, 1.0);
    animate(fish, fish._initAnimationStep);
    const climb = (Math.atan2(Math.abs(fish.vector[1]), Math.abs(fish.vector[0])) * 180) / Math.PI;
    assert(climb < 25, "near level at hand-over");
    assert(fish.rotate[1] === facesItsHeading(fish));
  });
}

fishTest("a short entry keeps easing to cruise while swimming", () => {
  const fish = new DrawingFish(null);
  holdEffort(fish, 1.0);
  fish._waterResistance = 0.98;
  fish._initAnimationStep = 60; // Too short to slow all the way: 0.02 * 0.98^60 = 0.006
  animate(fish, 60);
  assert(fish._animationStage === "swim" && speedOf(fish) > 1.5 * fish._cruiseSpeed);
  animate(fish, 120);
  assertClose(speedOf(fish), fish._cruiseSpeed);
});

fishTest("the exit speeds up smoothly to double pace", () => {
  const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [0.003, 0.0, 0.0]);
  const cruise = speedOf(fish);
  const speeds = [cruise];
  fish.goAway();
  speeds.push(speedOf(fish));
  for (let i = 0; i < 120; i++) {
    fish.animation();
    speeds.push(speedOf(fish));
  }
  const ratios = speeds.slice(1).map((speed, i) => speed / speeds[i]);
  assert(Math.max(...ratios) <= 1.1 && Math.min(...ratios) >= 1.0 - 1e-9, "exit speed must ramp, never snap");
  assertClose(speeds[speeds.length - 1], 2 * cruise, { rtol: 0.02 });
});

fishTest("the head turn follows how fast the fish changes depth", () => {
  const fish = swimmingFishAt(0.0, 0.0);
  fish._depthPeriod = 600;
  const turns = [];
  for (let i = 0; i < 600; i++) {
    fish.animation();
    turns.push(fish.shaderParams[2]);
  }
  assert(Math.max(...turns) > 0.5 * HEAD_TURN && Math.min(...turns) < -0.5 * HEAD_TURN, "turns both ways");
  assert(Math.max(...turns.map(Math.abs)) <= HEAD_TURN + 1e-9);
  const jumps = turns.slice(1).map((turn, i) => Math.abs(turn - turns[i]));
  assert(Math.max(...jumps) < 0.02 * HEAD_TURN, "smooth throughout");
  // Fastest depth change is at the quarter points, so the head is most turned there (a little
  // late because of the easing) and near straight at the near and far points
  const most = turns.indexOf(Math.max(...turns));
  const least = turns.indexOf(Math.min(...turns));
  assert(150 <= most && most <= 175 && 450 <= least && least <= 475, `extremes at ticks ${most} and ${least}`);
  assert(Math.abs(turns[299]) < 0.2 * HEAD_TURN && Math.abs(turns[599]) < 0.2 * HEAD_TURN);
});

fishTest("the head eases straight while leaving", () => {
  const fish = swimmingFishAt(0.0, 0.0);
  fish._depthPeriod = 600;
  animate(fish, 160);
  assert(Math.abs(fish.shaderParams[2]) > 0.4);
  fish.goAway();
  const turns = [];
  for (let i = 0; i < 60; i++) {
    fish.animation();
    turns.push(Math.abs(fish.shaderParams[2]));
  }
  assert(turns[turns.length - 1] < 0.01);
  assert(turns.slice(1).every((turn, i) => turn <= turns[i]), "decays monotonically");
});

fishTest("the head straightens when the depth cycle is held", () => {
  const fish = swimmingFishAt(0.0, 0.0);
  fish._depthPeriod = 600;
  animate(fish, 150);
  assert(Math.abs(fish.shaderParams[2]) > 0.1);
  fish.holdDepth = true;
  for (let i = 0; i < 120; i++) {
    fish.animation();
    fish.holdDepth = true; // Would normally be re-set each tick by preventDepthCrossings
  }
  assert(Math.abs(fish.shaderParams[2]) < 0.01, "eased back to straight while held");
});

for (const [vx, vy, baseSign, rotateY, expectedSign, situation] of [
  [0.003, 0.002, 1, 0.0, 1, "facing right, diving (y grows downwards): nose tips down"],
  [0.003, -0.002, 1, 0.0, -1, "facing right, climbing"],
  [-0.003, 0.002, -1, 0.0, -1, "facing left by mirror, diving: the z rotation is applied before the mirror"],
  [-0.003, -0.002, -1, 0.0, 1, "facing left by mirror, climbing"],
  [-0.003, 0.002, 1, 180.0, 1, "facing left by a y turn (the usual case after a wall), diving"],
  [-0.003, -0.002, 1, 180.0, -1, "facing left by a y turn, climbing"],
]) {
  fishTest(`a fish pitches its nose toward where it is heading: ${situation}`, () => {
    const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [vx, vy, 0.0]);
    fish._baseScale[0] = baseSign * Math.abs(fish._baseScale[0]);
    fish.rotate[1] = rotateY;
    fish._steer = () => {}; // Hold the heading; steering would level it during the run
    animate(fish, 150); // Long enough for the eased pitch to settle
    const pitch = fish.rotate[2];
    assert(Math.sign(pitch) === expectedSign);
    assert(0 < Math.abs(pitch) && Math.abs(pitch) <= MAX_PITCH);
    const climb = (Math.atan2(Math.abs(vy), Math.abs(vx)) * 180) / Math.PI;
    assert(isClose(Math.abs(pitch), pitchForClimb(climb), { atol: 1.0 }));
  });
}

fishTest("pitch ignores the small wander of a level cruise", () => {
  // A fish cruising level keeps crossing a few degrees above and below level; it must not rock
  const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [0.003, 0.0, 0.0]);
  fish._steer = () => {}; // Drive the heading by hand
  let worst = 0.0;
  for (let tick = 0; tick < 600; tick++) {
    const climb = ((Math.floor(tick / 30) % 2 === 0 ? 4.0 : -4.0) * Math.PI) / 180; // Dithering every half second
    fish.vector = [0.003 * Math.cos(climb), 0.003 * Math.sin(climb), 0.0];
    fish.animation();
    worst = Math.max(worst, Math.abs(fish.rotate[2]));
  }
  assert(worst < 0.5, `pitch rocked to ${worst.toFixed(2)} degrees on a level cruise`);
});

test("the pitch mapping has a deadband and a ceiling", () => {
  assert(pitchForClimb(0.0) === 0.0 && pitchForClimb(PITCH_DEADBAND) === 0.0);
  assert(0 < pitchForClimb(PITCH_DEADBAND + 5) && pitchForClimb(PITCH_DEADBAND + 5) < MAX_PITCH);
  assertClose(pitchForClimb((PITCH_DEADBAND + PITCH_FULL_AT) / 2), MAX_PITCH / 2); // Linear ramp
  assert(pitchForClimb(PITCH_FULL_AT) === MAX_PITCH && pitchForClimb(90.0) === MAX_PITCH);
});

fishTest("pitch is slight and eases", () => {
  const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [0.001, 0.003, 0.0]); // Steep dive, 72 degrees
  const pitches = [];
  for (let i = 0; i < 60; i++) {
    fish.animation();
    pitches.push(fish.rotate[2]);
  }
  assert(Math.max(...pitches) <= MAX_PITCH + 1e-9);
  const jumps = pitches.map((pitch, i) => Math.abs(pitch - (i === 0 ? 0.0 : pitches[i - 1])));
  assert(Math.max(...jumps) < 0.3 * MAX_PITCH, "no snap");
  fish.vector = [0.003, 0.0, 0.0]; // Level off
  animate(fish, 120);
  assert(Math.abs(fish.rotate[2]) < 0.5);
});

fishTest("overlap accounts for a pitched fish", () => {
  const a = swimmingFishAt(0.0, 0.0);
  const b = swimmingFishAt(1.05, 0.0); // Just clear when both are level (half widths 0.5 + 0.5)
  assert(!a.overlaps(b));
  a.rotate[2] = 20.0; // Pitched: its rotated rectangle reaches further in x
  assert(a.overlaps(b));
});

fishTest("pitch eases level while leaving", () => {
  const fish = swimmingFishBeyond([0.0, -0.2, 0.0], [0.002, 0.003, 0.0]); // Steep dive
  fish._steer = () => {};
  animate(fish, 150);
  assert(fish.rotate[2] > 15);
  fish.goAway();
  const pitches = [];
  for (let i = 0; i < 90; i++) {
    fish.animation();
    pitches.push(Math.abs(fish.rotate[2]));
  }
  assert(pitches[pitches.length - 1] < 0.5);
  assert(pitches.slice(1).every((pitch, i) => pitch <= pitches[i]), "decays monotonically");
});
