from __future__ import annotations

import math

import numpy as np

from engine.drawing import Drawing
from engine.shaders import ShaderProgram
from ocean.drawingbubble import DrawingBubble

# Tail beat as seen from the side. A fish swings its tail sideways, out of the picture plane,
# so on screen the tail foreshortens toward the body rather than bending up and down. The
# swing grows toward the tail tip and travels along the body. params.x is the fish's own beat
# phase (advanced in animation() from its tempo and effort) and params.y the peak swing.
FISH_TRANSFORM = """
const float TAIL_START = 0.1;   // Sprite x where the flexible tail begins; the head is toward +x
vec4 transform(vec3 p) {
    float tail = clamp((TAIL_START - p.x) / (TAIL_START + 0.5), 0.0, 1.0);
    float swing = params.y * tail * tail * sin(params.x - tail * 2.0);
    float x = TAIL_START + (p.x - TAIL_START) * cos(swing);
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
        self.vector = np.array([0, 0.02, 0.0])
        self.is_alive = True  # The fish will be deleted from the drawing list when it False

        self._left = -1.5
        self._right = 1.5
        self._top = -0.7
        self._bottom = 0.3

        # Randomly choose entry direction (0: left, 1: right, 2: top, 3: bottom)
        entry_direction = np.random.randint(4)
        if entry_direction == 0:  # From left
            self.position = np.array([-2.0, np.random.uniform(self._top, self._bottom), 0.0])
            self.vector = np.array([0.02, 0.0, 0.0])
        elif entry_direction == 1:  # From right
            self.position = np.array([2.0, np.random.uniform(self._top, self._bottom), 0.0])
            self.vector = np.array([-0.02, 0.0, 0.0])
            self._base_scale[0] = -abs(self._base_scale[0])  # Face left
        elif entry_direction == 2:  # From top
            self.position = np.array([np.random.uniform(self._left, self._right), -1, 0.0])
            self.vector = np.array([0.0, 0.02, 0.0])
        else:  # From bottom
            self.position = np.array([np.random.uniform(self._left, self._right), 0.5, 0.0])
            self.vector = np.array([0.0, -0.02, 0.0])

        # Randomly flip horizontal direction for variety
        if np.random.randint(2) == 0 and (entry_direction in [2, 3]):  # Only for vertical entry
            self._base_scale[0] = -self._base_scale[0]
            self.vector[0] = np.random.uniform(-0.01, 0.01)  # Add slight horizontal movement
        self.scale = self._base_scale.copy()

        # Parameters for animations
        self._animation_stage = "init"
        self._init_animation_step = np.random.randint(60, 180)  # Random start time between 1-3 seconds at 60fps
        self._water_resistance = np.random.uniform(0.95, 0.98)
        self._depth_period = np.random.randint(600, 1500)  # 10-25 seconds at 60 ticks per second
        self._depth_tick = 0
        self._distance = 0.0
        self._speed_factor = 1.0
        self.hold_depth = False  # Set each tick by prevent_depth_crossings
        self.extent = np.array(extent, dtype=float)

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

    def _init_fish_velocity(self) -> None:
        """
        Setup initial values for velocity vector
        :return:
        """
        self.vector = np.array([np.random.uniform(0.002, 0.003), np.random.uniform(0.001, 0.002), 0.0])
        if self._base_scale[0] < 0:
            self.vector[0] = -self.vector[0]
        if np.random.randint(2) == 0:
            self.vector[1] = -self.vector[1]

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

        if self._animation_stage == "init":
            self._init_animation_step -= 1
            self._bubble_random_frequency += 0.1
            self.vector[1] *= self._water_resistance
            # Finis init animation
            if self._init_animation_step == 0:
                self._init_fish_velocity()
                self._animation_stage = "swim"

        elif self._animation_stage == "swim":
            if not self.hold_depth:
                self._depth_tick += 1
            self._apply_distance(distance_cycle(self._depth_tick, self._depth_period))

            # Beyond a border and still heading out: turn around once. Checking the heading
            # matters because a fish can start swimming already past a border (a long entry
            # overshoots), and flipping on position alone would turn it every tick forever.
            heading_out_x = (self.position[0] > self._right and self.vector[0] > 0) or (
                self.position[0] < self._left and self.vector[0] < 0
            )
            if heading_out_x:
                self.vector[0] = -self.vector[0]
                self.rotation_vector[1] = 5.0

            heading_out_y = (self.position[1] > self._bottom and self.vector[1] > 0) or (
                self.position[1] < self._top and self.vector[1] < 0
            )
            if heading_out_y:
                self.vector[1] = -self.vector[1]

            self.rotate[1] = (self.rotate[1] + self.rotation_vector[1]) % 360

            if self.rotate[1] % 180 == 0:
                self.rotation_vector[1] = 0.0

        elif self._animation_stage == "finish":
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
        my_size, their_size = np.abs(self.scale[:2]), np.abs(other.scale[:2])
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

    def _apply_distance(self, distance: float) -> None:
        """
        Shrink, slow, dim and push back the fish according to how far away it is
        :param distance: 0 when nearest, 1 at the far point
        :return:
        """
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
        self.vector[1] = 0.0
        self.vector[0] *= 2
        self._speed_factor = 1.0  # Leave at full pace whatever the distance was
        self._effort_target = EFFORT_LEVELS["burst"]  # Flee
        self._animation_stage = "finish"
