from __future__ import annotations

import math

import numpy as np

from engine.drawing import Drawing
from engine.shaders import ShaderProgram
from ocean.drawingbubble import DrawingBubble

# Tail beat and head turn as seen from the side. A fish swings its tail sideways, out of the
# picture plane, so on screen the tail foreshortens toward the body rather than bending up and
# down; the swing grows toward the tail tip and travels along the body. The head does the
# same, gently and without wiggling, when the fish is swimming away or toward the viewer:
# a turn out of the picture plane foreshortens the head end. params.x is the fish's own beat
# phase (advanced in animation() from its tempo and effort), params.y the peak tail swing and
# params.z the head turn angle.
FISH_TRANSFORM = """
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
"""

# Swimming effort. A fish drifts between resting, cruising and bursting (hunting or fleeing),
# easing from one level to the next; its speed and tail beat follow. tempo is a per-fish
# multiplier on both, so no two fish move alike.
EFFORT_LEVELS = {"rest": 0.45, "cruise": 1.0, "burst": 1.9}
EFFORT_WEIGHTS = [0.3, 0.5, 0.2]
TICKS_PER_SECOND = 60  # Animation ticks per second, matching main_ocean.TICK_SECONDS
EFFORT_DWELL_TICKS = (2 * TICKS_PER_SECOND, 7 * TICKS_PER_SECOND)
EFFORT_EASING = 0.04  # Fraction of the remaining change applied per tick (about a second to settle)
TEMPO_RANGE = (0.8, 1.25)
# Steering. A fish turns by rotating its heading a little each tick, never by flipping its
# velocity, so a wall produces an arc rather than a bounce. Within TURN_MARGIN of a border it
# turns away from it, the harder the closer; otherwise it wanders gently and drifts back toward
# level. The sprite's facing follows the heading's x sign through a y-rotation.
TURN_MARGIN_X = 0.45  # Distance from a side border at which a fish starts turning away
TURN_MARGIN_Y = 0.2  # Top and bottom: enough for a bursting fish's turn radius, small against the 1.0-tall band
TURN_RATE = 0.035  # Radians per tick at full steer: a 180 degree turn in about 1.5 s
WANDER = 0.004  # Random heading drift per tick, radians
LEVELLING = 0.0015  # Pull of the heading back toward horizontal, radians per tick
FACE_RATE = 5.0  # Degrees per tick of the y-rotation that turns the sprite to face its heading
# Pitch: the sprite tips its nose toward where it is heading when climbing or diving, slightly.
# A level cruise wanders a few degrees either side of level all the time; the deadband keeps
# that from rocking the fish, and the pitch grows from there to its ceiling by PITCH_FULL_AT.
MAX_PITCH = 20.0  # Degrees of z-rotation from PITCH_FULL_AT on
PITCH_DEADBAND = 5.0  # Climb or dive angles below this, in degrees, do not pitch the fish
PITCH_FULL_AT = 45.0  # Climb or dive angle, in degrees, at which the pitch reaches MAX_PITCH
PITCH_EASING = 0.05  # Fraction of the remaining change applied per tick (about a second to settle)


def pitch_for_climb(climb_degrees: float) -> float:
    """
    Pitch for a heading's climb or dive angle (unsigned)
    :param climb_degrees: Angle between the heading and horizontal
    :return: Degrees of pitch, 0 inside the deadband, MAX_PITCH from PITCH_FULL_AT on
    """
    share = (abs(climb_degrees) - PITCH_DEADBAND) / (PITCH_FULL_AT - PITCH_DEADBAND)
    return MAX_PITCH * max(0.0, min(1.0, share))


# Entry and exit. A fish arrives fast and eases out to its cruising speed before it starts
# swimming (the velocity carries over unchanged, so there is no jump at the hand-over), and
# a fish told to leave ramps up to double its cruising speed rather than snapping to it.
ENTRY_SPEED = 0.02
ENTRY_SIDEWAYS = (0.4, 0.8)  # Horizontal share of a vertical entry's heading, before normalising
ENTRY_LEVELLING = 0.02  # Radians per tick the heading levels during the entry (about 1 degree)
CRUISE_SPEED_RANGE = (0.002, 0.003)
EXIT_SPEED_MULTIPLIER = 2.0
EXIT_EASING = 1.03  # Speed multiplier per tick while ramping up to leave (about a second to double)
# Head turn: how far the head angles out of the picture plane at the fastest depth change,
# and how quickly the angle follows (so a depth hold eases the head straight, never snaps)
HEAD_TURN = 0.5  # Radians at the fastest depth change (about 30 degrees)
HEAD_EASING = 0.08
TAIL_BEAT_HZ = 1.6  # Beat rate at cruise effort and tempo 1
TAIL_SWING = 0.6  # Peak swing at the tail tip at cruise, radians (about 35 degrees)


# A swimming fish cycles between near and far. At the far point it is drawn at FAR_SCALE of its
# size, moves at FAR_SPEED of its pace, is tinted down to FAR_TINT and sits at depth FAR_Z so that
# nearer fish draw in front of it.
FAR_SCALE = 0.45
FAR_SPEED = 0.5
FAR_TINT = 0.7
FAR_Z = -0.5


def distance_cycle(tick: int, period: int) -> float:
    """
    How far away the fish is at a point in its cycle
    :param tick: Animation ticks since the cycle began
    :param period: Ticks for one full cycle, near to far and back
    :return: 0 when nearest, 1 at the far point
    """
    return 0.5 * (1 - math.cos(2 * math.pi * tick / period))


def prevent_depth_crossings(fishes: list[DrawingFish]) -> None:
    """
    Hold the depth cycle of any fish whose next step would cross the depth of a fish it
    overlaps on screen, so two overlapping fish keep their draw order (a swap would look like
    one passing through the other). Fish that overlap without crossing keep cycling.
    :param fishes: All fish in the scene
    :return:
    """
    for fish in fishes:
        fish.hold_depth = False
    for i, fish in enumerate(fishes):
        for other in fishes[i + 1 :]:
            if not (fish.overlaps(other) or fish.overlaps(other, after_step=True)):
                continue  # Not overlapping now and not about to: both may move freely
            # Either fish may move this tick; hold as few as keep them from meeting or passing.
            # A move only counts as safe if it stays on its side of the other fish's CURRENT depth
            # too, because a later pair may hold that other fish after this decision is made.
            order = np.sign(fish.position[2] - other.position[2])
            fish_next = fish.position[2] if fish.hold_depth else fish.next_z()
            other_next = other.position[2] if other.hold_depth else other.next_z()
            fish_ok = np.sign(fish_next - other.position[2]) == order
            other_ok = np.sign(fish.position[2] - other_next) == order
            if order == 0:
                # Same depth: the renderer draws the earlier sprite on top, so hold that one and let
                # the later one step deeper; the order that forms matches what is already on screen
                fish.hold_depth = True
            elif not (fish_ok or other_ok):
                fish.hold_depth = other.hold_depth = True
            elif fish_ok and other_ok and np.sign(fish_next - other_next) == order:
                continue  # Both may move
            elif fish_ok:
                other.hold_depth = True  # Let this one move; the other would meet it
            else:
                fish.hold_depth = True


class DrawingFish(Drawing):
    """
    Sprite for drawing of fish
    """

    def __init__(
        self,
        texid: int,
        grid_x: int = 5,
        grid_y: int = 5,
        shader: ShaderProgram | None = None,
        bubble_texture_id: int = 0,
        extent: tuple[float, float] = (1.0, 1.0),
    ):
        """
        Set default position of fish and select default vector of moving
        :param texid: ID of texture
        :param grid_x: Mesh elements along axis X
        :param grid_y: Mesh elements along axis Y
        :param shader: Sprite program, or None for the renderer's default
        :param bubble_texture_id: ID of a bubble texture
        :param extent: Fraction of the canvas width and height the painted fish covers
        """
        super().__init__(texid, grid_x, grid_y, shader)
        self.is_transparent = True  # Mark fish as transparent for proper rendering
        self._base_scale = np.array([1.0, 0.75, 0.3])  # Size when nearest; the sign of x is the facing direction
        self.is_alive = True  # The fish will be deleted from the drawing list when it False

        self._left = -1.5
        self._right = 1.5
        self._top = -0.7
        self._bottom = 0.3

        # Randomly choose entry direction (0: left, 1: right, 2: top, 3: bottom)
        entry_direction = np.random.randint(4)
        if entry_direction == 0:  # From left
            self.position = np.array([-2.0, np.random.uniform(self._top, self._bottom), 0.0])
            heading = np.array([1.0, 0.0])
        elif entry_direction == 1:  # From right
            self.position = np.array([2.0, np.random.uniform(self._top, self._bottom), 0.0])
            heading = np.array([-1.0, 0.0])
        elif entry_direction == 2:  # From top
            self.position = np.array([np.random.uniform(self._left, self._right), -1, 0.0])
            heading = np.array([0.0, 1.0])
        else:  # From bottom
            self.position = np.array([np.random.uniform(self._left, self._right), 0.5, 0.0])
            heading = np.array([0.0, -1.0])

        # Vertical entries always come in at an angle, so the fish has a side to face and levels
        # out during the entry instead of diving straight into the band
        if entry_direction in [2, 3]:
            heading[0] = np.random.choice([-1.0, 1.0]) * np.random.uniform(*ENTRY_SIDEWAYS)
            heading /= np.linalg.norm(heading)
        if heading[0] < 0:
            self._base_scale[0] = -abs(self._base_scale[0])  # Face the way we are going
        self.scale = self._base_scale.copy()
        self.vector = np.array([heading[0] * ENTRY_SPEED, heading[1] * ENTRY_SPEED, 0.0])
        self._cruise_speed = np.random.uniform(*CRUISE_SPEED_RANGE)
        self._exit_speed = 0.0

        # Parameters for animations
        self._animation_stage = "init"
        self._init_animation_step = np.random.randint(60, 180)  # Random start time between 1-3 seconds at 60fps
        self._water_resistance = np.random.uniform(0.95, 0.98)
        self._depth_period = np.random.randint(600, 1500)  # 10-25 seconds at 60 ticks per second
        self._depth_tick = 0
        self._distance = 0.0
        self._speed_factor = 1.0
        self._head_turn = 0.0
        self.hold_depth = False  # Set each tick by prevent_depth_crossings
        self.extent = np.array(extent, dtype=float)
        self._turn_bias = 0.0  # Which way round a wall turn goes once committed (+1 or -1), 0 when not turning

        # Temperament
        self.tempo = np.random.uniform(*TEMPO_RANGE)
        self.effort = EFFORT_LEVELS["cruise"]
        self._effort_target = self.effort
        self._effort_ticks_left = np.random.randint(*EFFORT_DWELL_TICKS)
        self._tail_phase = 0.0

        # To animate bubbles
        self._bubble_texture_id = bubble_texture_id
        self._bubble_random_frequency = 2
        self._bubble_deviation_x = 0
        self._bubble_speed_y = -0.01
        self._bubbles = []

    def _set_speed(self, speed: float) -> None:
        """Keep the heading, change the pace"""
        current = math.hypot(self.vector[0], self.vector[1])
        if current > 0:
            self.vector[:2] *= speed / current

    def _start_swimming(self) -> None:
        """
        Hand over from the entry to swimming; the velocity carries over unchanged
        :return:
        """
        self._bubble_random_frequency = 500
        self._bubble_deviation_x = 0.1
        self._bubble_speed_y = -0.005

    def _process_bubbles(self) -> None:
        # randomly create bubble
        if np.random.randint(int(self._bubble_random_frequency)) == 0:
            bubble_x = np.random.uniform(self.position[0], self.position[0] + self.scale[0] / 2)
            bubble = DrawingBubble(self._bubble_texture_id, start_x=bubble_x, start_y=self.position[1])
            bubble.deviation_x = self._bubble_deviation_x
            bubble.speed_y = self._bubble_speed_y
            # Bubbles are as far away as the fish that made them
            bubble.scale = bubble.scale * (1 - (1 - FAR_SCALE) * self._distance)
            bubble.color = self.color.copy()
            bubble.position[2] = self.position[2]
            self._bubbles.append(bubble)

        # delete bubbles when they left the screen
        self._bubbles = [bubble for bubble in self._bubbles if bubble.position[1] >= -1]

    def animation(self) -> None:
        """
        Logic of movement of the fish
        :return:
        """
        self._update_effort()
        self._beat_tail()
        self.position += self.vector * self._speed_factor * self.effort
        self._process_bubbles()

        if self._animation_stage != "finish":
            # Ease out from the entry speed to the cruising speed; a short entry may hand over
            # before the fish has slowed all the way, so this carries on into swimming
            self._set_speed(
                max(self._cruise_speed, math.hypot(self.vector[0], self.vector[1]) * self._water_resistance)
            )

        if self._animation_stage == "init":
            self._init_animation_step -= 1
            self._bubble_random_frequency += 0.1
            self._level(ENTRY_LEVELLING)
            self._face_heading()
            # Finis init animation
            if self._init_animation_step == 0:
                self._start_swimming()
                self._animation_stage = "swim"

        elif self._animation_stage == "swim":
            if not self.hold_depth:
                self._depth_tick += 1
            self._apply_distance(distance_cycle(self._depth_tick, self._depth_period))

            self._steer()
            self._face_heading()

        elif self._animation_stage == "finish":
            self._turn_head(0.0)  # No longer changing depth, so the head eases straight
            speed = math.hypot(self.vector[0], self.vector[1])
            # Ramp toward the exit pace from either side, never snapping
            self._set_speed(
                min(self._exit_speed, speed * EXIT_EASING)
                if speed < self._exit_speed
                else max(self._exit_speed, speed / EXIT_EASING)
            )
            self._face_heading()
            if self.position[0] > self._right + 1.0 or self.position[0] < self._left - 1.0:
                self.is_alive = False

    def overlaps(self, other: DrawingFish, after_step: bool = False) -> bool:
        """
        Whether this fish's painted rectangle overlaps another's on screen
        :param other: Another fish
        :param after_step: Judge where both fish will be after their next movement step
        :return: True when the two painted areas overlap in x and y
        """
        mine, theirs = self.position[:2], other.position[:2]
        my_size, their_size = self._footprint(), other._footprint()
        if after_step:
            mine = mine + self.vector[:2] * self._speed_factor * self._next_effort()
            theirs = theirs + other.vector[:2] * other._speed_factor * other._next_effort()
            # A fish coming nearer grows a little each tick: judge with the larger size
            my_size = np.maximum(my_size, self._next_size())
            their_size = np.maximum(their_size, other._next_size())
        half = (my_size * self.extent + their_size * other.extent) / 2
        return bool(np.all(np.abs(mine - theirs) < half))

    def _next_effort(self) -> float:
        """Effort after the easing step that precedes the next move"""
        return self.effort + (self._effort_target - self.effort) * EFFORT_EASING

    def _footprint(self) -> np.ndarray:
        """Width and height of the box around the drawn, pitched sprite"""
        w, h = np.abs(self.scale[:2])
        c, s = abs(math.cos(math.radians(self.rotate[2]))), abs(math.sin(math.radians(self.rotate[2])))
        return np.array([w * c + h * s, h * c + w * s])

    def _next_size(self) -> np.ndarray:
        """Drawn width and height after the next depth step"""
        distance = (
            distance_cycle(self._depth_tick + 1, self._depth_period)
            if self._animation_stage == "swim"
            else self._distance
        )
        return np.abs(self._base_scale[:2]) * (1 - (1 - FAR_SCALE) * distance)

    def next_z(self) -> float:
        """
        Depth this fish would be at after its next cycle step (unchanged unless swimming)
        :return: z position
        """
        if self._animation_stage != "swim":
            return float(self.position[2])
        return FAR_Z * distance_cycle(self._depth_tick + 1, self._depth_period)

    def _steer(self) -> None:
        """
        Rotate the heading: away from any border within its turn margin (a fish that starts past a
        border, as a long entry can leave it, just turns at the full rate), otherwise a gentle
        wander with a pull back toward level. Speed is kept; only the direction changes.
        :return:
        """
        x, y = self.position[:2]
        away = np.array(
            [
                min(max((x - (self._right - TURN_MARGIN_X)) / TURN_MARGIN_X, 0.0), 1.0)
                - min(max(((self._left + TURN_MARGIN_X) - x) / TURN_MARGIN_X, 0.0), 1.0),
                min(max((y - (self._bottom - TURN_MARGIN_Y)) / TURN_MARGIN_Y, 0.0), 1.0)
                - min(max(((self._top + TURN_MARGIN_Y) - y) / TURN_MARGIN_Y, 0.0), 1.0),
            ]
        )
        heading = math.atan2(self.vector[1], self.vector[0])
        speed = math.hypot(self.vector[0], self.vector[1])
        if np.any(away):
            urgency = min(float(np.linalg.norm(away)), 1.0)
            target = math.atan2(-away[1], -away[0])
            delta = (target - heading + math.pi) % (2 * math.pi) - math.pi
            if abs(delta) > math.pi - 0.05:
                # Heading straight at the wall: either way round is as short. Commit once to the
                # way whose first sideways step points toward the middle of the tank, and keep it
                # while the tie lasts, or the choice would flicker each tick. A positive heading
                # change moves the fish sideways along (-sin h, cos h), so the sign depends on
                # which way it is facing, not just on which side of the middle it is.
                if self._turn_bias == 0.0:
                    middle_x, middle_y = (self._left + self._right) / 2, (self._top + self._bottom) / 2
                    sideways = -math.sin(heading) * (middle_x - x) + math.cos(heading) * (middle_y - y)
                    self._turn_bias = 1.0 if sideways >= 0 else -1.0
                delta = self._turn_bias * math.pi
            else:
                self._turn_bias = 0.0
            heading += max(-TURN_RATE * urgency, min(TURN_RATE * urgency, delta))
        else:
            self._turn_bias = 0.0
            heading += np.random.uniform(-WANDER, WANDER)
            heading = self._levelled(heading, LEVELLING)
        self.vector[0] = speed * math.cos(heading)
        self.vector[1] = speed * math.sin(heading)

    @staticmethod
    def _levelled(heading: float, rate: float) -> float:
        """Heading pulled toward horizontal (whichever way is nearer) by at most rate"""
        level = 0.0 if math.cos(heading) >= 0 else math.pi
        toward_level = (level - heading + math.pi) % (2 * math.pi) - math.pi
        return heading + max(-rate, min(rate, toward_level))

    def _level(self, rate: float) -> None:
        """Turn the heading toward horizontal by at most rate, keeping the speed"""
        speed = math.hypot(self.vector[0], self.vector[1])
        heading = self._levelled(math.atan2(self.vector[1], self.vector[0]), rate)
        self.vector[0] = speed * math.cos(heading)
        self.vector[1] = speed * math.sin(heading)

    def _face_heading(self) -> None:
        """
        Turn the sprite about y, a few degrees per tick, so it faces the way it is heading
        :return:
        """
        facing_forward = (self.vector[0] >= 0) == (self._base_scale[0] >= 0)
        target = 0.0 if facing_forward else 180.0
        delta = (target - self.rotate[1] + 180) % 360 - 180
        self.rotate[1] = (self.rotate[1] + max(-FACE_RATE, min(FACE_RATE, delta))) % 360
        self.rotation_vector[1] = 0.0 if self.rotate[1] == target else FACE_RATE
        self._pitch_to_heading()

    def _pitch_to_heading(self) -> None:
        """
        Tip the nose toward the heading's climb or dive, within MAX_PITCH, eased
        :return:
        """
        climb = math.degrees(math.atan2(self.vector[1], abs(self.vector[0])))  # Positive is down on screen
        # The z-rotation is applied in sprite space before the mirror that faces a fish left, so
        # a mirrored sprite needs the opposite sign to tip the same way on screen
        target = math.copysign(1.0, self._base_scale[0]) * math.copysign(pitch_for_climb(climb), climb)
        self.rotate[2] += (target - self.rotate[2]) * PITCH_EASING

    def _update_effort(self) -> None:
        """
        Pick a new effort level now and then, and ease toward the current one
        :return:
        """
        if self._animation_stage == "swim":
            self._effort_ticks_left -= 1
            if self._effort_ticks_left <= 0:
                # Always change gear: re-picking the current level would leave a fish static for two dwells
                others = [
                    (level, weight)
                    for level, weight in zip(EFFORT_LEVELS.values(), EFFORT_WEIGHTS, strict=True)
                    if level != self._effort_target
                ]
                weights = np.array([weight for _, weight in others]) / sum(weight for _, weight in others)
                self._effort_target = others[np.random.choice(len(others), p=weights)][0]
                self._effort_ticks_left = np.random.randint(*EFFORT_DWELL_TICKS)
        self.effort += (self._effort_target - self.effort) * EFFORT_EASING

    def _beat_tail(self) -> None:
        """
        Advance the tail beat: faster and wider the harder the fish works
        :return:
        """
        # Damped on purpose: a bursting fish (effort 1.9) beats 1.45x faster and 1.36x wider,
        # not 1.9x, which would look frantic; a resting one still beats at 0.73x
        rate = TAIL_BEAT_HZ * self.tempo * (0.5 + 0.5 * self.effort)
        self._tail_phase += 2 * math.pi * rate / TICKS_PER_SECOND
        self.shader_params[0] = self._tail_phase
        self.shader_params[1] = TAIL_SWING * (0.6 + 0.4 * self.effort)

    def _turn_head(self, target: float) -> None:
        """Ease the head's out-of-plane angle toward a target"""
        self._head_turn += (target - self._head_turn) * HEAD_EASING
        self.shader_params[2] = self._head_turn

    def _apply_distance(self, distance: float) -> None:
        """
        Shrink, slow, dim and push back the fish according to how far away it is
        :param distance: 0 when nearest, 1 at the far point
        :return:
        """
        # Angle the head by how fast the depth is changing, relative to the fastest the cycle
        # ever changes it (at its quarter points); receding turns one way, returning the other
        fastest = math.pi / self._depth_period
        self._turn_head(HEAD_TURN * max(-1.0, min(1.0, (distance - self._distance) / fastest)))
        self._distance = distance
        self.scale = self._base_scale * (1 - (1 - FAR_SCALE) * distance)
        self.color = np.full(3, 1 - (1 - FAR_TINT) * distance)
        self.position[2] = FAR_Z * distance
        self._speed_factor = 1 - (1 - FAR_SPEED) * distance

    def get_child_sprites(self) -> list[Drawing]:
        """
        Return list of bubbles
        :return: List of bubbles
        """
        return self._bubbles

    def go_away(self) -> None:
        """
        Start animation of fish swimming away
        :return:
        """
        # Leave level, ramping up to double speed, the way the fish is already going if that is
        # at all sideways, otherwise the way it is facing (a steering fish can be mid-turn,
        # heading nearly straight up or down, and the finish stage does not steer)
        speed = math.hypot(self.vector[0], self.vector[1])
        if abs(self.vector[0]) > 0.2 * speed:
            direction = math.copysign(1.0, self.vector[0])
        else:
            faces_base_way = (
                abs(self.rotate[1] - 180.0) > 90.0
            )  # Within 90 degrees of rotate 0; edge-on counts as turned
            direction = math.copysign(1.0, self._base_scale[0]) * (1.0 if faces_base_way else -1.0)
        self.vector = np.array([speed * direction, 0.0, 0.0])
        self._exit_speed = EXIT_SPEED_MULTIPLIER * self._cruise_speed  # A culled entrant settles to a normal exit pace
        self._speed_factor = 1.0  # Leave at full pace whatever the distance was
        self._effort_target = EFFORT_LEVELS["burst"]  # Flee
        self._animation_stage = "finish"
