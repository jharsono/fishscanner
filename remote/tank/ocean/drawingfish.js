import { Drawing } from "../engine/drawing.js";
import { choice, randint, uniform } from "../engine/random.js";
import { DrawingBubble } from "./drawingbubble.js";

// Tail beat and head turn as seen from the side. A fish swings its tail sideways, out of the
// picture plane, so on screen the tail foreshortens toward the body rather than bending up and
// down; the swing grows toward the tail tip and travels along the body. The head does the
// same, gently and without wiggling, when the fish is swimming away or toward the viewer:
// a turn out of the picture plane foreshortens the head end. params.x is the fish's own beat
// phase (advanced in animation() from its tempo and effort), params.y the peak tail swing and
// params.z the head turn angle.
export const FISH_TRANSFORM = `
const float TAIL_START = 0.1;   // Sprite x where the flexible tail begins; the head is toward +x
const float HEAD_START = 0.2;   // Sprite x where the head begins turning
vec4 transform(vec3 p) {
    float tail = clamp((TAIL_START - p.x) / (TAIL_START + 0.5), 0.0, 1.0);
    float swing = params.y * tail * tail * sin(params.x - tail * 2.0);
    float x = TAIL_START + (p.x - TAIL_START) * cos(swing);
    float head = clamp((x - HEAD_START) / (0.5 - HEAD_START), 0.0, 1.0);
    x = HEAD_START + (x - HEAD_START) * cos(params.z * head);
    return model * vec4(x, p.y, p.z, 1.0);
}
`;

// Swimming effort. A fish drifts between resting, cruising and bursting (hunting or fleeing),
// easing from one level to the next; its speed and tail beat follow. tempo is a per-fish
// multiplier on both, so no two fish move alike.
export const EFFORT_LEVELS = { rest: 0.45, cruise: 1.0, burst: 1.9 };
const EFFORT_WEIGHTS = [0.3, 0.5, 0.2];
const TICKS_PER_SECOND = 60; // Animation ticks per second, matching main.js's TICK_SECONDS
const EFFORT_DWELL_TICKS = [2 * TICKS_PER_SECOND, 7 * TICKS_PER_SECOND];
const EFFORT_EASING = 0.04; // Fraction of the remaining change applied per tick (about a second to settle)
const TEMPO_RANGE = [0.8, 1.25];
// Steering. A fish turns by rotating its heading a little each tick, never by flipping its
// velocity, so a wall produces an arc rather than a bounce. Within TURN_MARGIN of a border it
// turns away from it, the harder the closer; otherwise it wanders gently and drifts back toward
// level. The sprite's facing follows the heading's x sign through a y-rotation.
const TURN_MARGIN_X = 0.45; // Distance from a side border at which a fish starts turning away
const TURN_MARGIN_Y = 0.2; // Top and bottom: enough for a bursting fish's turn radius, small against the 1.0-tall band
export const TURN_RATE = 0.035; // Radians per tick at full steer: a 180 degree turn in about 1.5 s
export const WANDER = 0.004; // Random heading drift per tick, radians
const LEVELLING = 0.0015; // Pull of the heading back toward horizontal, radians per tick
const FACE_RATE = 5.0; // Degrees per tick of the y-rotation that turns the sprite to face its heading
// Pitch: the sprite tips its nose toward where it is heading when climbing or diving, slightly.
// A level cruise wanders a few degrees either side of level all the time; the deadband keeps
// that from rocking the fish, and the pitch grows from there to its ceiling by PITCH_FULL_AT.
export const MAX_PITCH = 20.0; // Degrees of z-rotation from PITCH_FULL_AT on
export const PITCH_DEADBAND = 5.0; // Climb or dive angles below this, in degrees, do not pitch the fish
export const PITCH_FULL_AT = 45.0; // Climb or dive angle, in degrees, at which the pitch reaches MAX_PITCH
const PITCH_EASING = 0.05; // Fraction of the remaining change applied per tick (about a second to settle)

/**
 * Pitch for a heading's climb or dive angle (unsigned)
 * @param {number} climbDegrees Angle between the heading and horizontal
 * @returns {number} Degrees of pitch, 0 inside the deadband, MAX_PITCH from PITCH_FULL_AT on
 */
export function pitchForClimb(climbDegrees) {
  const share = (Math.abs(climbDegrees) - PITCH_DEADBAND) / (PITCH_FULL_AT - PITCH_DEADBAND);
  return MAX_PITCH * Math.max(0.0, Math.min(1.0, share));
}

// Entry and exit. A fish arrives fast and eases out to its cruising speed before it starts
// swimming (the velocity carries over unchanged, so there is no jump at the hand-over), and
// a fish told to leave ramps up to double its cruising speed rather than snapping to it.
export const ENTRY_SPEED = 0.02;
const ENTRY_SIDEWAYS = [0.4, 0.8]; // Horizontal share of a vertical entry's heading, before normalising
export const ENTRY_LEVELLING = 0.02; // Radians per tick the heading levels during the entry (about 1 degree)
const CRUISE_SPEED_RANGE = [0.002, 0.003];
const EXIT_SPEED_MULTIPLIER = 2.0;
const EXIT_EASING = 1.03; // Speed multiplier per tick while ramping up to leave (about a second to double)
// Head turn: how far the head angles out of the picture plane at the fastest depth change,
// and how quickly the angle follows (so a depth hold eases the head straight, never snaps)
export const HEAD_TURN = 0.5; // Radians at the fastest depth change (about 30 degrees)
const HEAD_EASING = 0.08;
const TAIL_BEAT_HZ = 1.6; // Beat rate at cruise effort and tempo 1
const TAIL_SWING = 0.6; // Peak swing at the tail tip at cruise, radians (about 35 degrees)

// A swimming fish cycles between near and far. At the far point it is drawn at FAR_SCALE of its
// size, moves at FAR_SPEED of its pace, is tinted down to FAR_TINT and sits at depth FAR_Z so that
// nearer fish draw in front of it.
export const FAR_SCALE = 0.45;
export const FAR_SPEED = 0.5;
export const FAR_TINT = 0.7;
export const FAR_Z = -0.5;

/** a modulo n with the sign of n, like Python's %; JavaScript's % keeps the sign of a */
export function mod(a, n) {
  return ((a % n) + n) % n;
}

/** magnitude with the sign of sign, like Python's math.copysign (so -0 counts as negative) */
export function copysign(magnitude, sign) {
  return sign < 0 || Object.is(sign, -0) ? -Math.abs(magnitude) : Math.abs(magnitude);
}

function degrees(radians) {
  return (radians * 180) / Math.PI;
}

function radians(degreesValue) {
  return (degreesValue * Math.PI) / 180;
}

function clamp01(value) {
  return Math.min(Math.max(value, 0.0), 1.0);
}

/**
 * How far away the fish is at a point in its cycle
 * @param {number} tick Animation ticks since the cycle began
 * @param {number} period Ticks for one full cycle, near to far and back
 * @returns {number} 0 when nearest, 1 at the far point
 */
export function distanceCycle(tick, period) {
  return 0.5 * (1 - Math.cos((2 * Math.PI * tick) / period));
}

/**
 * Hold the depth cycle of any fish whose next step would cross the depth of a fish it
 * overlaps on screen, so two overlapping fish keep their draw order (a swap would look like
 * one passing through the other). Fish that overlap without crossing keep cycling.
 * @param {DrawingFish[]} fishes All fish in the scene
 */
export function preventDepthCrossings(fishes) {
  for (const fish of fishes) {
    fish.holdDepth = false;
  }
  for (let i = 0; i < fishes.length; i++) {
    const fish = fishes[i];
    for (const other of fishes.slice(i + 1)) {
      if (!(fish.overlaps(other) || fish.overlaps(other, { afterStep: true }))) {
        continue; // Not overlapping now and not about to: both may move freely
      }
      // Either fish may move this tick; hold as few as keep them from meeting or passing.
      // A move only counts as safe if it stays on its side of the other fish's CURRENT depth
      // too, because a later pair may hold that other fish after this decision is made.
      const order = Math.sign(fish.position[2] - other.position[2]);
      const fishNext = fish.holdDepth ? fish.position[2] : fish.nextZ();
      const otherNext = other.holdDepth ? other.position[2] : other.nextZ();
      const fishOk = Math.sign(fishNext - other.position[2]) === order;
      const otherOk = Math.sign(fish.position[2] - otherNext) === order;
      if (order === 0) {
        // Same depth: the renderer draws the earlier sprite on top, so hold that one and let
        // the later one step deeper; the order that forms matches what is already on screen
        fish.holdDepth = true;
      } else if (!(fishOk || otherOk)) {
        fish.holdDepth = other.holdDepth = true;
      } else if (fishOk && otherOk && Math.sign(fishNext - otherNext) === order) {
        continue; // Both may move
      } else if (fishOk) {
        other.holdDepth = true; // Let this one move; the other would meet it
      } else {
        fish.holdDepth = true;
      }
    }
  }
}

/** Sprite for drawing of fish */
export class DrawingFish extends Drawing {
  /**
   * Set default position of fish and select default vector of moving
   * @param {WebGLTexture|null} texture Texture of the scanned fish
   * @param {{gridX?: number, gridY?: number, shader?: object|null, bubbleTexture?: WebGLTexture|null,
   *   extent?: number[]}} options Mesh elements along X and Y, the sprite program (null for the
   *   renderer's default), the bubble texture, and the fraction of the canvas width and height the
   *   painted fish covers
   */
  constructor(texture, { gridX = 5, gridY = 5, shader = null, bubbleTexture = null, extent = [1.0, 1.0] } = {}) {
    super(texture, { gridX, gridY, shader });
    this.isTransparent = true; // Mark fish as transparent for proper rendering
    this._baseScale = [1.0, 0.75, 0.3]; // Size when nearest; the sign of x is the facing direction
    this.isAlive = true; // The fish will be deleted from the drawing list when it false

    this._left = -1.5;
    this._right = 1.5;
    this._top = -0.7;
    this._bottom = 0.3;

    // Randomly choose entry direction (0: left, 1: right, 2: top, 3: bottom)
    const entryDirection = randint(4);
    let heading;
    if (entryDirection === 0) {
      // From left
      this.position = [-2.0, uniform(this._top, this._bottom), 0.0];
      heading = [1.0, 0.0];
    } else if (entryDirection === 1) {
      // From right
      this.position = [2.0, uniform(this._top, this._bottom), 0.0];
      heading = [-1.0, 0.0];
    } else if (entryDirection === 2) {
      // From top
      this.position = [uniform(this._left, this._right), -1, 0.0];
      heading = [0.0, 1.0];
    } else {
      // From bottom
      this.position = [uniform(this._left, this._right), 0.5, 0.0];
      heading = [0.0, -1.0];
    }

    // Vertical entries always come in at an angle, so the fish has a side to face and levels
    // out during the entry instead of diving straight into the band
    if (entryDirection === 2 || entryDirection === 3) {
      heading[0] = choice([-1.0, 1.0]) * uniform(...ENTRY_SIDEWAYS);
      const length = Math.hypot(heading[0], heading[1]);
      heading = [heading[0] / length, heading[1] / length];
    }
    if (heading[0] < 0) {
      this._baseScale[0] = -Math.abs(this._baseScale[0]); // Face the way we are going
    }
    this.scale = [...this._baseScale];
    this.vector = [heading[0] * ENTRY_SPEED, heading[1] * ENTRY_SPEED, 0.0];
    this._cruiseSpeed = uniform(...CRUISE_SPEED_RANGE);
    this._exitSpeed = 0.0;

    // Parameters for animations
    this._animationStage = "init";
    this._initAnimationStep = randint(60, 180); // Random start time between 1-3 seconds at 60fps
    this._waterResistance = uniform(0.95, 0.98);
    this._depthPeriod = randint(600, 1500); // 10-25 seconds at 60 ticks per second
    this._depthTick = 0;
    this._distance = 0.0;
    this._speedFactor = 1.0;
    this._headTurn = 0.0;
    this.holdDepth = false; // Set each tick by preventDepthCrossings
    this.extent = [...extent];
    this._turnBias = 0.0; // Which way round a wall turn goes once committed (+1 or -1), 0 when not turning

    // Temperament
    this.tempo = uniform(...TEMPO_RANGE);
    this.effort = EFFORT_LEVELS.cruise;
    this._effortTarget = this.effort;
    this._effortTicksLeft = randint(...EFFORT_DWELL_TICKS);
    this._tailPhase = 0.0;

    // To animate bubbles
    this._bubbleTexture = bubbleTexture;
    this._bubbleRandomFrequency = 2;
    this._bubbleDeviationX = 0;
    this._bubbleSpeedY = -0.01;
    this._bubbles = [];
  }

  /** Keep the heading, change the pace */
  _setSpeed(speed) {
    const current = Math.hypot(this.vector[0], this.vector[1]);
    if (current > 0) {
      this.vector[0] *= speed / current;
      this.vector[1] *= speed / current;
    }
  }

  /** Hand over from the entry to swimming; the velocity carries over unchanged */
  _startSwimming() {
    this._bubbleRandomFrequency = 500;
    this._bubbleDeviationX = 0.1;
    this._bubbleSpeedY = -0.005;
  }

  _processBubbles() {
    // randomly create bubble
    if (randint(Math.trunc(this._bubbleRandomFrequency)) === 0) {
      const bubbleX = uniform(this.position[0], this.position[0] + this.scale[0] / 2);
      const bubble = new DrawingBubble(this._bubbleTexture, { startX: bubbleX, startY: this.position[1] });
      bubble.deviationX = this._bubbleDeviationX;
      bubble.speedY = this._bubbleSpeedY;
      // Bubbles are as far away as the fish that made them
      const shrink = 1 - (1 - FAR_SCALE) * this._distance;
      bubble.scale = bubble.scale.map((value) => value * shrink);
      bubble.color = [...this.color];
      bubble.position[2] = this.position[2];
      this._bubbles.push(bubble);
    }

    // delete bubbles when they left the screen
    this._bubbles = this._bubbles.filter((bubble) => bubble.position[1] >= -1);
  }

  /** Logic of movement of the fish */
  animation() {
    this._updateEffort();
    this._beatTail();
    for (let i = 0; i < 3; i++) {
      this.position[i] += this.vector[i] * this._speedFactor * this.effort;
    }
    this._processBubbles();

    if (this._animationStage !== "finish") {
      // Ease out from the entry speed to the cruising speed; a short entry may hand over
      // before the fish has slowed all the way, so this carries on into swimming
      this._setSpeed(
        Math.max(this._cruiseSpeed, Math.hypot(this.vector[0], this.vector[1]) * this._waterResistance),
      );
    }

    if (this._animationStage === "init") {
      this._initAnimationStep -= 1;
      this._bubbleRandomFrequency += 0.1;
      this._level(ENTRY_LEVELLING);
      this._faceHeading();
      // Finish init animation
      if (this._initAnimationStep === 0) {
        this._startSwimming();
        this._animationStage = "swim";
      }
    } else if (this._animationStage === "swim") {
      if (!this.holdDepth) {
        this._depthTick += 1;
      }
      this._applyDistance(distanceCycle(this._depthTick, this._depthPeriod));

      this._steer();
      this._faceHeading();
    } else if (this._animationStage === "finish") {
      this._turnHead(0.0); // No longer changing depth, so the head eases straight
      const speed = Math.hypot(this.vector[0], this.vector[1]);
      // Ramp toward the exit pace from either side, never snapping
      this._setSpeed(
        speed < this._exitSpeed
          ? Math.min(this._exitSpeed, speed * EXIT_EASING)
          : Math.max(this._exitSpeed, speed / EXIT_EASING),
      );
      this._faceHeading();
      if (this.position[0] > this._right + 1.0 || this.position[0] < this._left - 1.0) {
        this.isAlive = false;
      }
    }
  }

  /**
   * Whether this fish's painted rectangle overlaps another's on screen
   * @param {DrawingFish} other Another fish
   * @param {{afterStep?: boolean}} options Judge where both fish will be after their next movement step
   * @returns {boolean} True when the two painted areas overlap in x and y
   */
  overlaps(other, { afterStep = false } = {}) {
    let mine = this.position.slice(0, 2);
    let theirs = other.position.slice(0, 2);
    let mySize = this._footprint();
    let theirSize = other._footprint();
    if (afterStep) {
      const myPace = this._speedFactor * this._nextEffort();
      const theirPace = other._speedFactor * other._nextEffort();
      mine = mine.map((value, i) => value + this.vector[i] * myPace);
      theirs = theirs.map((value, i) => value + other.vector[i] * theirPace);
      // A fish coming nearer grows a little each tick: judge with the larger size
      const myNext = this._nextSize();
      const theirNext = other._nextSize();
      mySize = mySize.map((value, i) => Math.max(value, myNext[i]));
      theirSize = theirSize.map((value, i) => Math.max(value, theirNext[i]));
    }
    return [0, 1].every(
      (i) => Math.abs(mine[i] - theirs[i]) < (mySize[i] * this.extent[i] + theirSize[i] * other.extent[i]) / 2,
    );
  }

  /** Effort after the easing step that precedes the next move */
  _nextEffort() {
    return this.effort + (this._effortTarget - this.effort) * EFFORT_EASING;
  }

  /** Width and height of the box around the drawn, pitched sprite */
  _footprint() {
    const w = Math.abs(this.scale[0]);
    const h = Math.abs(this.scale[1]);
    const c = Math.abs(Math.cos(radians(this.rotate[2])));
    const s = Math.abs(Math.sin(radians(this.rotate[2])));
    return [w * c + h * s, h * c + w * s];
  }

  /** Drawn width and height after the next depth step */
  _nextSize() {
    const distance =
      this._animationStage === "swim" ? distanceCycle(this._depthTick + 1, this._depthPeriod) : this._distance;
    const shrink = 1 - (1 - FAR_SCALE) * distance;
    return [Math.abs(this._baseScale[0]) * shrink, Math.abs(this._baseScale[1]) * shrink];
  }

  /**
   * Depth this fish would be at after its next cycle step (unchanged unless swimming)
   * @returns {number} z position
   */
  nextZ() {
    if (this._animationStage !== "swim") {
      return this.position[2];
    }
    return FAR_Z * distanceCycle(this._depthTick + 1, this._depthPeriod);
  }

  /**
   * Rotate the heading: away from any border within its turn margin (a fish that starts past a
   * border, as a long entry can leave it, just turns at the full rate), otherwise a gentle
   * wander with a pull back toward level. Speed is kept; only the direction changes.
   */
  _steer() {
    const [x, y] = this.position;
    const away = [
      clamp01((x - (this._right - TURN_MARGIN_X)) / TURN_MARGIN_X) -
        clamp01((this._left + TURN_MARGIN_X - x) / TURN_MARGIN_X),
      clamp01((y - (this._bottom - TURN_MARGIN_Y)) / TURN_MARGIN_Y) -
        clamp01((this._top + TURN_MARGIN_Y - y) / TURN_MARGIN_Y),
    ];
    let heading = Math.atan2(this.vector[1], this.vector[0]);
    const speed = Math.hypot(this.vector[0], this.vector[1]);
    if (away[0] !== 0 || away[1] !== 0) {
      const urgency = Math.min(Math.hypot(away[0], away[1]), 1.0);
      const target = Math.atan2(-away[1], -away[0]);
      let delta = mod(target - heading + Math.PI, 2 * Math.PI) - Math.PI;
      if (Math.abs(delta) > Math.PI - 0.05) {
        // Heading straight at the wall: either way round is as short. Commit once to the
        // way whose first sideways step points toward the middle of the tank, and keep it
        // while the tie lasts, or the choice would flicker each tick. A positive heading
        // change moves the fish sideways along (-sin h, cos h), so the sign depends on
        // which way it is facing, not just on which side of the middle it is.
        if (this._turnBias === 0.0) {
          const middleX = (this._left + this._right) / 2;
          const middleY = (this._top + this._bottom) / 2;
          const sideways = -Math.sin(heading) * (middleX - x) + Math.cos(heading) * (middleY - y);
          this._turnBias = sideways >= 0 ? 1.0 : -1.0;
        }
        delta = this._turnBias * Math.PI;
      } else {
        this._turnBias = 0.0;
      }
      heading += Math.max(-TURN_RATE * urgency, Math.min(TURN_RATE * urgency, delta));
    } else {
      this._turnBias = 0.0;
      heading += uniform(-WANDER, WANDER);
      heading = DrawingFish._levelled(heading, LEVELLING);
    }
    this.vector[0] = speed * Math.cos(heading);
    this.vector[1] = speed * Math.sin(heading);
  }

  /** Heading pulled toward horizontal (whichever way is nearer) by at most rate */
  static _levelled(heading, rate) {
    const level = Math.cos(heading) >= 0 ? 0.0 : Math.PI;
    const towardLevel = mod(level - heading + Math.PI, 2 * Math.PI) - Math.PI;
    return heading + Math.max(-rate, Math.min(rate, towardLevel));
  }

  /** Turn the heading toward horizontal by at most rate, keeping the speed */
  _level(rate) {
    const speed = Math.hypot(this.vector[0], this.vector[1]);
    const heading = DrawingFish._levelled(Math.atan2(this.vector[1], this.vector[0]), rate);
    this.vector[0] = speed * Math.cos(heading);
    this.vector[1] = speed * Math.sin(heading);
  }

  /** Turn the sprite about y, a few degrees per tick, so it faces the way it is heading */
  _faceHeading() {
    const facingForward = this.vector[0] >= 0 === this._baseScale[0] >= 0;
    const target = facingForward ? 0.0 : 180.0;
    const delta = mod(target - this.rotate[1] + 180, 360) - 180;
    this.rotate[1] = mod(this.rotate[1] + Math.max(-FACE_RATE, Math.min(FACE_RATE, delta)), 360);
    this.rotationVector[1] = this.rotate[1] === target ? 0.0 : FACE_RATE;
    this._pitchToHeading();
  }

  /** Tip the nose toward the heading's climb or dive, within MAX_PITCH, eased */
  _pitchToHeading() {
    const climb = degrees(Math.atan2(this.vector[1], Math.abs(this.vector[0]))); // Positive is down on screen
    // The z-rotation is applied in sprite space before the mirror that faces a fish left, so
    // a mirrored sprite needs the opposite sign to tip the same way on screen
    const target = copysign(1.0, this._baseScale[0]) * copysign(pitchForClimb(climb), climb);
    this.rotate[2] += (target - this.rotate[2]) * PITCH_EASING;
  }

  /** Pick a new effort level now and then, and ease toward the current one */
  _updateEffort() {
    if (this._animationStage === "swim") {
      this._effortTicksLeft -= 1;
      if (this._effortTicksLeft <= 0) {
        // Always change gear: re-picking the current level would leave a fish static for two dwells
        const others = Object.values(EFFORT_LEVELS)
          .map((level, i) => [level, EFFORT_WEIGHTS[i]])
          .filter(([level]) => level !== this._effortTarget);
        const total = others.reduce((sum, [, weight]) => sum + weight, 0);
        this._effortTarget = choice(
          others.map(([level]) => level),
          others.map(([, weight]) => weight / total),
        );
        this._effortTicksLeft = randint(...EFFORT_DWELL_TICKS);
      }
    }
    this.effort += (this._effortTarget - this.effort) * EFFORT_EASING;
  }

  /** Advance the tail beat: faster and wider the harder the fish works */
  _beatTail() {
    // Damped on purpose: a bursting fish (effort 1.9) beats 1.45x faster and 1.36x wider,
    // not 1.9x, which would look frantic; a resting one still beats at 0.73x
    const rate = TAIL_BEAT_HZ * this.tempo * (0.5 + 0.5 * this.effort);
    this._tailPhase += (2 * Math.PI * rate) / TICKS_PER_SECOND;
    this.shaderParams[0] = this._tailPhase;
    this.shaderParams[1] = TAIL_SWING * (0.6 + 0.4 * this.effort);
  }

  /** Ease the head's out-of-plane angle toward a target */
  _turnHead(target) {
    this._headTurn += (target - this._headTurn) * HEAD_EASING;
    this.shaderParams[2] = this._headTurn;
  }

  /**
   * Shrink, slow, dim and push back the fish according to how far away it is
   * @param {number} distance 0 when nearest, 1 at the far point
   */
  _applyDistance(distance) {
    // Angle the head by how fast the depth is changing, relative to the fastest the cycle
    // ever changes it (at its quarter points); receding turns one way, returning the other
    const fastest = Math.PI / this._depthPeriod;
    this._turnHead(HEAD_TURN * Math.max(-1.0, Math.min(1.0, (distance - this._distance) / fastest)));
    this._distance = distance;
    const shrink = 1 - (1 - FAR_SCALE) * distance;
    this.scale = this._baseScale.map((value) => value * shrink);
    const tint = 1 - (1 - FAR_TINT) * distance;
    this.color = [tint, tint, tint];
    this.position[2] = FAR_Z * distance;
    this._speedFactor = 1 - (1 - FAR_SPEED) * distance;
  }

  /** Return list of bubbles */
  getChildSprites() {
    return this._bubbles;
  }

  /** Start animation of fish swimming away */
  goAway() {
    // Leave level, ramping up to double speed, the way the fish is already going if that is
    // at all sideways, otherwise the way it is facing (a steering fish can be mid-turn,
    // heading nearly straight up or down, and the finish stage does not steer)
    const speed = Math.hypot(this.vector[0], this.vector[1]);
    let direction;
    if (Math.abs(this.vector[0]) > 0.2 * speed) {
      direction = copysign(1.0, this.vector[0]);
    } else {
      const facesBaseWay = Math.abs(this.rotate[1] - 180.0) > 90.0; // Within 90 degrees of rotate 0; edge-on counts as turned
      direction = copysign(1.0, this._baseScale[0]) * (facesBaseWay ? 1.0 : -1.0);
    }
    this.vector = [speed * direction, 0.0, 0.0];
    this._exitSpeed = EXIT_SPEED_MULTIPLIER * this._cruiseSpeed; // A culled entrant settles to a normal exit pace
    this._speedFactor = 1.0; // Leave at full pace whatever the distance was
    this._effortTarget = EFFORT_LEVELS.burst; // Flee
    this._animationStage = "finish";
  }
}
