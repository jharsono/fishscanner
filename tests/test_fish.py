"""Sprite animation logic, run without an OpenGL context (meshes are created lazily on first render)."""

import numpy as np
import pytest

from ocean.drawingbubble import DrawingBubble
from ocean.drawingfish import DrawingFish


@pytest.fixture(autouse=True)
def seed():
    np.random.seed(0)


def test_fish_can_be_built_without_a_gl_context():
    fish = DrawingFish(texid=1)
    assert fish.is_alive
    assert fish.is_transparent


def test_all_offscreen_bubbles_are_removed_in_one_step():
    fish = DrawingFish(texid=1)
    fish._bubble_random_frequency = 10**9  # Never spawn new bubbles during the test
    for _ in range(6):
        bubble = DrawingBubble(texid=2, start_x=0.0, start_y=-2.0)  # Already above the top edge
        fish._bubbles.append(bubble)
    fish.animation()
    assert fish.get_child_sprites() == []


def test_fish_that_goes_away_dies_once_off_screen():
    fish = DrawingFish(texid=1)
    for _ in range(fish._init_animation_step + 1):
        fish.animation()  # Finish the entry animation
    fish.go_away()
    for _ in range(5000):
        fish.animation()
        if not fish.is_alive:
            break
    assert not fish.is_alive


def test_renderer_draws_bubbles_as_children_of_fish():
    from engine.renderer import Renderer

    fish = DrawingFish(texid=1)
    bubble = DrawingBubble(texid=2, start_x=0.0, start_y=0.0)
    fish._bubbles.append(bubble)
    assert Renderer.all_sprites([fish]) == [fish, bubble]
    assert bubble.is_transparent


def start_swimming(fish: DrawingFish) -> None:
    for _ in range(fish._init_animation_step + 1):
        fish.animation()


def test_distance_cycle_is_near_at_both_ends_and_far_in_the_middle():
    from ocean.drawingfish import distance_cycle

    assert distance_cycle(0, 600) == 0.0
    assert np.isclose(distance_cycle(300, 600), 1.0)
    assert np.isclose(distance_cycle(600, 600), 0.0)


def test_fish_shrinks_into_the_distance_and_grows_back():
    from ocean.drawingfish import FAR_SCALE

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 600
    base = abs(fish.scale[0])
    sizes = []
    for _ in range(600):
        fish.animation()
        sizes.append(abs(fish.scale[0]))
    assert np.isclose(min(sizes), base * FAR_SCALE, rtol=0.01)
    assert np.isclose(sizes[-1], base, rtol=0.01)  # Back to its original size after one full cycle
    assert max(sizes) <= base * 1.001  # Never larger than the original


def test_facing_direction_survives_the_distance_cycle():
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 200
    facing = np.sign(fish.scale[0])
    for _ in range(200):
        fish.animation()
        assert np.sign(fish.scale[0]) == facing


def test_far_fish_moves_slower_dims_and_sits_behind():
    from ocean.drawingfish import FAR_SPEED, FAR_Z

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 600
    before = fish.position.copy()
    fish.animation()
    near_step = np.linalg.norm((fish.position - before)[:2])
    assert np.isclose(fish.position[2], 0.0, atol=1e-3) and np.allclose(fish.color, 1.0, atol=1e-3)
    for _ in range(298):
        fish.animation()
    before = fish.position.copy()
    fish.animation()  # Tick 300 of 600: the far point
    far_step = np.linalg.norm((fish.position - before)[:2])
    assert np.isclose(far_step / near_step, FAR_SPEED, rtol=0.02)
    assert np.isclose(fish.position[2], FAR_Z, rtol=0.01)
    assert fish.color[0] < 1.0


def test_left_facing_fish_keeps_facing_left_through_the_cycle():
    np.random.seed(1)  # Enters from the right, so it faces left
    fish = DrawingFish(texid=1)
    assert fish._base_scale[0] < 0
    start_swimming(fish)
    fish._depth_period = 300
    for _ in range(300):
        fish.animation()
        assert fish.scale[0] < 0


def test_no_jump_between_entry_and_swimming():
    fish = DrawingFish(texid=1)
    for _ in range(fish._init_animation_step - 1):
        fish.animation()
    before = (fish.scale.copy(), fish.color.copy(), fish.position[2])
    fish.animation()  # Last entry tick switches to swimming
    fish.animation()  # First swimming tick
    assert np.allclose(fish.scale, before[0], atol=1e-4)
    assert np.allclose(fish.color, before[1], atol=1e-4)
    assert np.isclose(fish.position[2], before[2], atol=1e-4)


def test_far_point_values_are_exact():
    from ocean.drawingfish import FAR_SCALE, FAR_TINT, FAR_Z

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 600
    fish._depth_tick = 0
    for _ in range(300):
        fish.animation()
    assert np.allclose(np.abs(fish.scale), fish._base_scale.__abs__() * FAR_SCALE)
    assert np.allclose(fish.color, FAR_TINT)
    assert np.isclose(fish.position[2], FAR_Z)


def test_bubbles_inherit_the_parent_fish_distance():
    from ocean.drawingfish import FAR_SCALE, FAR_TINT, FAR_Z

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 600
    fish._depth_tick = 0
    for _ in range(300):
        fish.animation()
    fish._bubble_random_frequency = 1  # Spawn on the next step
    fish.animation()
    bubble = fish.get_child_sprites()[-1]
    assert np.isclose(bubble.position[2], FAR_Z)
    assert np.allclose(bubble.color, FAR_TINT)
    assert bubble.scale[0] <= 0.15 * FAR_SCALE + 1e-9  # Bubble sizes are drawn up to 0.15, then shrunk with the fish


def test_fish_leaving_from_the_far_point_exits_at_full_pace():
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 600
    for _ in range(300):
        fish.animation()
    fish.go_away()
    before = fish.position.copy()
    pace = abs(fish.vector[0])
    fish.animation()
    assert np.isclose(abs((fish.position - before)[0]), pace * fish.effort)


def count_direction_changes(fish: DrawingFish, axis: int, ticks: int) -> int:
    changes = 0
    last = np.sign(fish.vector[axis])
    for _ in range(ticks):
        fish.animation()
        if np.sign(fish.vector[axis]) != last:
            changes += 1
            last = np.sign(fish.vector[axis])
    return changes


def hold_effort(fish: DrawingFish, effort: float) -> None:
    fish.effort = fish._effort_target = effort
    fish._effort_ticks_left = 10**6


def swimming_fish_beyond(position: list[float], vector: list[float]) -> DrawingFish:
    """A fish already past a border and still heading out, as a long entry animation can leave it."""
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 10**6  # Keep full speed for a clear count
    hold_effort(fish, 1.0)
    fish.position = np.array(position)
    fish.vector = np.array(vector)
    fish._cruise_speed = float(np.hypot(vector[0], vector[1]))  # This is its pace; nothing eases it away
    return fish


@pytest.mark.parametrize(
    ("position", "vector", "axis"),
    [
        ([2.0, 0.0, 0.0], [0.003, 0.0, 0.0], 0),  # Beyond the right border
        ([-2.0, 0.0, 0.0], [-0.003, 0.0, 0.0], 0),  # Beyond the left border
        ([0.0, 0.6, 0.0], [0.0, 0.002, 0.0], 1),  # Below the bottom bound
        ([0.0, -1.0, 0.0], [0.0, -0.002, 0.0], 1),  # Above the top bound
    ],
)
def test_fish_beyond_a_border_turns_once_and_comes_back(position, vector, axis):
    fish = swimming_fish_beyond(position, vector)
    assert count_direction_changes(fish, axis, 600) == 1
    assert fish._left < fish.position[0] < fish._right
    assert fish._top < fish.position[1] < fish._bottom
    faces_its_heading = 0 if (fish.vector[0] >= 0) == (fish._base_scale[0] >= 0) else 180
    assert fish.rotate[1] == faces_its_heading and fish.rotation_vector[1] == 0


def test_fish_beyond_a_corner_turns_once_and_comes_back():
    fish = swimming_fish_beyond([2.0, 0.6, 0.0], [0.003, 0.002, 0.0])
    assert count_direction_changes(fish, 0, 600) == 1  # One arc, not a bounce on each wall
    assert fish._left < fish.position[0] < fish._right
    assert fish._top < fish.position[1] < fish._bottom
    assert fish.rotate[1] == 180 and fish.rotation_vector[1] == 0  # Entered heading right, left heading left


def test_each_fish_has_its_own_tempo():
    tempos = set()
    for seed in range(5):
        np.random.seed(seed)
        tempos.add(round(DrawingFish(texid=1).tempo, 4))
    assert len(tempos) == 5


def test_effort_ebbs_and_flows_within_bounds():
    from ocean.drawingfish import EFFORT_LEVELS

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    efforts = []
    for _ in range(60 * 60):  # A minute of swimming
        fish.animation()
        efforts.append(fish.effort)
    assert min(EFFORT_LEVELS.values()) - 1e-6 <= min(efforts)
    assert max(efforts) <= max(EFFORT_LEVELS.values()) + 1e-6
    assert max(efforts) - min(efforts) > 0.5, "effort never changed"
    # Transitions are eased, never a jump
    assert max(abs(b - a) for a, b in zip(efforts[:-1], efforts[1:], strict=True)) < 0.1


def test_speed_and_tail_beat_follow_effort():
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 10**6
    hold_effort(fish, 0.5)
    before = fish.position.copy()
    phase_before = fish._tail_phase
    fish.animation()
    slow_step = np.linalg.norm((fish.position - before)[:2])
    slow_beat = fish._tail_phase - phase_before
    hold_effort(fish, 2.0)
    before = fish.position.copy()
    phase_before = fish._tail_phase
    fish.animation()
    fast_step = np.linalg.norm((fish.position - before)[:2])
    fast_beat = fish._tail_phase - phase_before
    assert np.isclose(fast_step / slow_step, 4.0, rtol=0.01)
    assert fast_beat > slow_beat * 1.5
    assert fish.shader_params[0] == fish._tail_phase
    assert fish.shader_params[1] > 0


def test_fish_told_to_leave_bursts():
    from ocean.drawingfish import EFFORT_LEVELS

    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish.go_away()
    assert fish._effort_target == EFFORT_LEVELS["burst"]


def test_effort_always_changes_gear_when_re_picked():
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    seen = []
    for _ in range(60 * 120):
        before = fish._effort_target
        fish.animation()
        if fish._effort_target != before:
            seen.append((before, fish._effort_target))
    assert len(seen) >= 10
    assert all(a != b for a, b in seen)


def test_fish_end_up_out_of_phase():
    phases = set()
    for seed in range(4):
        np.random.seed(seed)
        fish = DrawingFish(texid=1)
        start_swimming(fish)
        for _ in range(600):
            fish.animation()
        phases.add(round(fish._tail_phase % (2 * np.pi), 2))
    assert len(phases) == 4


def swimming_fish_at(x: float, y: float) -> DrawingFish:
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    hold_effort(fish, 1.0)
    fish._depth_period = 600
    fish.position = np.array([x, y, 0.0])
    fish.vector = np.array([0.0, 0.0, 0.0])  # Hold still so the test is about depth, not motion
    fish._cruise_speed = 0.0
    return fish


def test_fish_overlap_is_judged_from_their_drawn_extents():
    a = swimming_fish_at(0.0, 0.0)
    b = swimming_fish_at(0.9, 0.0)  # Fish are 1.0 wide: edges touch at 0.5 vs 0.4
    c = swimming_fish_at(1.2, 0.0)
    assert a.overlaps(b) and b.overlaps(a)
    assert not a.overlaps(c)


def test_overlap_uses_the_painted_extent_not_the_whole_canvas():
    a = swimming_fish_at(0.0, 0.0)
    b = swimming_fish_at(0.7, 0.0)
    assert a.overlaps(b)  # Full quads (1.0 wide) overlap
    a.extent = b.extent = np.array([0.5, 1.0])  # Paint covers only the middle half of each canvas
    assert not a.overlaps(b)


def test_depth_cycles_continue_but_never_cross_while_overlapping():
    from ocean.drawingfish import prevent_depth_crossings

    a = swimming_fish_at(0.0, 0.0)  # Near (tick 0), heading away
    b = swimming_fish_at(0.3, 0.1)
    b._depth_tick = 300  # Far point, heading back toward the front: the two would meet
    for _ in range(300):
        prevent_depth_crossings([a, b])
        a.animation()
        b.animation()
        assert a.position[2] >= b.position[2]  # a stays in front for the whole overlap
    assert 0 < a._depth_tick <= 152 and 300 < b._depth_tick  # Both cycled up to the meeting point, then held
    b.position[0] = 2.0  # Now clear of each other
    held = (a._depth_tick, b._depth_tick)
    for _ in range(50):
        prevent_depth_crossings([a, b])
        a.animation()
        b.animation()
    assert a._depth_tick == held[0] + 50 and b._depth_tick == held[1] + 50  # Both resume


def test_many_fish_keep_cycling_and_never_pass_through_each_other():
    """Six fish with real-sized painted extents (scans cover ~0.75 x 0.85 of their canvas)."""
    from ocean.drawingfish import prevent_depth_crossings

    fishes = []
    for seed in range(6):
        np.random.seed(seed)
        fish = DrawingFish(texid=1, extent=(0.75, 0.85))
        start_swimming(fish)
        fishes.append(fish)
    advanced = [0] * 6
    crossings = 0
    for _ in range(3600):  # One minute
        before_z = [f.position[2] for f in fishes]
        before_tick = [f._depth_tick for f in fishes]
        prevent_depth_crossings(fishes)
        for f in fishes:
            f.animation()
        for i, f in enumerate(fishes):
            advanced[i] += f._depth_tick > before_tick[i]
            for k in range(i + 1, 6):
                if (
                    f.overlaps(fishes[k])
                    and np.sign(before_z[i] - before_z[k]) * np.sign(f.position[2] - fishes[k].position[2]) < 0
                ):
                    crossings += 1
    assert crossings == 0
    # Fish that travel together in arcs stay overlapped for long stretches, so a third of the
    # minute cycling on average, and never less than ten seconds for any fish, is the bar
    assert min(advanced) > 600 and np.mean(advanced) > 1200, f"fish spent too long held: {advanced}"


def test_overlap_lookahead_sees_fish_about_to_meet_or_grow_into_each_other():
    a = swimming_fish_at(0.0, 0.0)
    b = swimming_fish_at(1.2, 0.0)  # Just clear: half widths sum to 1.0 with full-canvas extents
    assert not a.overlaps(b) and not a.overlaps(b, after_step=True)
    b.vector = np.array([-0.3, 0.0, 0.0])  # Would step well into a next tick
    assert not a.overlaps(b) and a.overlaps(b, after_step=True)
    b.vector[:] = 0
    b._depth_tick = 299  # At the far point, small; next step it starts growing back
    b._apply_distance(1.0)
    b.position[0] = 0.5 + abs(b.scale[0]) / 2 + 1e-4  # Touching distance at the current, shrunken size
    assert not a.overlaps(b)
    b._depth_tick = 400  # Growing quickly on the way back
    assert a.overlaps(b, after_step=True)


def test_equal_depth_tie_holds_only_one_fish():
    from ocean.drawingfish import prevent_depth_crossings

    a = swimming_fish_at(0.0, 0.0)
    b = swimming_fish_at(0.2, 0.0)  # Both at depth tick 0, z 0, overlapping
    for _ in range(30):
        prevent_depth_crossings([a, b])
        a.animation()
        b.animation()
    assert (
        a._depth_tick != b._depth_tick and min(a._depth_tick, b._depth_tick) > 0
    )  # One waited a tick; an order formed
    # At equal depth the renderer draws the earlier sprite on top, so that one must stay on top
    assert a.position[2] > b.position[2]


def test_lookahead_predicts_the_eased_effort_not_the_current_one():
    a = swimming_fish_at(0.0, 0.0)
    b = swimming_fish_at(1.2, 0.0)  # Just clear at full-canvas extents
    b.vector = np.array([-0.05, 0.0, 0.0])
    b.effort = 0.0
    b._effort_target = 2.0  # The next move uses the eased effort, which is above zero
    assert a.overlaps(b, after_step=True) == (b._next_effort() * 0.05 > 0.2)
    b._effort_target = 0.0
    assert not a.overlaps(b, after_step=True)


def heading(fish: DrawingFish) -> float:
    return float(np.arctan2(fish.vector[1], fish.vector[0]))


def test_turn_at_a_wall_is_a_smooth_arc_not_a_bounce():
    from ocean.drawingfish import TURN_RATE

    fish = swimming_fish_beyond([1.2, -0.2, 0.0], [0.003, 0.0, 0.0])  # Inside the border, heading for it
    speed = np.linalg.norm(fish.vector[:2])
    headings = [heading(fish)]
    x_changes = 0
    for _ in range(400):
        before = np.sign(fish.vector[0])
        fish.animation()
        x_changes += np.sign(fish.vector[0]) != before
        headings.append(heading(fish))
        assert np.isclose(np.linalg.norm(fish.vector[:2]), speed, rtol=1e-6)  # Speed is kept, only direction turns
    steps = [abs((b - a + np.pi) % (2 * np.pi) - np.pi) for a, b in zip(headings[:-1], headings[1:], strict=True)]
    assert max(steps) <= TURN_RATE + 1e-9, "heading jumped instead of turning"
    assert x_changes == 1
    assert fish.vector[0] < 0 and fish.position[0] < fish._right + 0.1
    assert fish.rotate[1] == 180 and fish.rotation_vector[1] == 0


def test_fish_faces_the_way_it_is_heading_after_turning_twice():
    fish = swimming_fish_beyond([1.2, -0.2, 0.0], [0.003, 0.0, 0.0])
    for _ in range(400):
        fish.animation()
    assert fish.vector[0] < 0 and fish.rotate[1] == 180
    fish.position[0] = -1.2  # Carry it to the other wall still heading left
    for _ in range(400):
        fish.animation()
    assert fish.vector[0] > 0 and fish.rotate[1] == 0


@pytest.mark.parametrize("wall_x, vx", [(1.2, 0.003), (-1.2, -0.003)])
def test_turn_direction_curves_toward_the_middle_of_the_tank(wall_x, vx):
    """Straight at either side wall, clear of the top and bottom margins, so only the tie-break decides."""
    middle = -0.2
    low = swimming_fish_beyond([wall_x, 0.05, 0.0], [vx, 0.0, 0.0])  # Below the middle (y grows downwards)
    high = swimming_fish_beyond([wall_x, -0.45, 0.0], [vx, 0.0, 0.0])  # Above the middle
    for _ in range(90):
        low.animation()
        high.animation()
    assert low.position[1] < 0.05 and abs(low.position[1] - middle) < abs(0.05 - middle)
    assert high.position[1] > -0.45 and abs(high.position[1] - middle) < abs(-0.45 - middle)


def test_bursting_fish_straight_at_the_top_turns_before_leaving_the_screen():
    fish = swimming_fish_beyond([0.0, -0.3, 0.0], [0.0, -0.003, 0.0])  # Straight up at full pace
    hold_effort(fish, 1.9)
    lowest_y = 0.0
    for _ in range(300):
        fish.animation()
        lowest_y = min(lowest_y, fish.position[1])
    assert (
        lowest_y > fish._top - 0.07 and fish.vector[1] > 0
    )  # Turned back down within a small overshoot (0.12 margin: 0.094)


def test_fish_told_to_leave_from_a_vertical_heading_still_leaves():
    fish = swimming_fish_beyond([0.0, -0.2, 0.0], [0.0, -0.003, 0.0])  # Mid-turn, heading straight up
    fish.go_away()
    for _ in range(1500):
        fish.animation()
        if not fish.is_alive:
            break
    assert not fish.is_alive, f"still in the tank at {fish.position[:2]}"
    faces_its_heading = 0.0 if (fish.vector[0] >= 0) == (fish._base_scale[0] >= 0) else 180.0
    assert fish.rotate[1] == faces_its_heading  # Faced the way it left


@pytest.mark.parametrize("wall_y, vy", [(-0.55, -0.003), (0.15, 0.003)])
def test_turn_at_the_top_or_bottom_curves_toward_the_tank_centre(wall_y, vy):
    left = swimming_fish_beyond([-0.8, wall_y, 0.0], [0.0, vy, 0.0])
    right = swimming_fish_beyond([0.8, wall_y, 0.0], [0.0, vy, 0.0])
    for _ in range(90):
        left.animation()
        right.animation()
    assert left.position[0] > -0.8 and right.position[0] < 0.8  # Each arcs toward x = 0


def speed_of(fish: DrawingFish) -> float:
    return float(np.hypot(fish.vector[0], fish.vector[1]))


@pytest.mark.parametrize("seed", [0, 1, 3, 5])  # One seed per entry direction
def test_entry_eases_out_to_cruising_speed_with_no_jump_into_swimming(seed):
    from ocean.drawingfish import ENTRY_SPEED

    np.random.seed(seed)
    fish = DrawingFish(texid=1)
    hold_effort(fish, 1.0)
    assert np.isclose(speed_of(fish), ENTRY_SPEED)
    speeds = [speed_of(fish)]
    stage_changed_at = None
    for tick in range(fish._init_animation_step + 60):
        fish.animation()
        speeds.append(speed_of(fish))
        if stage_changed_at is None and fish._animation_stage == "swim":
            stage_changed_at = tick
    ratios = [b / a for a, b in zip(speeds[:-1], speeds[1:], strict=True)]
    assert max(ratios) <= 1.0 + 1e-9, "the fish sped up during its entry"
    assert min(ratios) >= 0.9, "a speed jump: entry speed must ease out, never snap"
    assert stage_changed_at is not None
    assert np.isclose(speeds[-1], fish._cruise_speed) and 0.002 <= fish._cruise_speed <= 0.003


@pytest.mark.parametrize("seed", [0, 1, 3, 5])
def test_entry_heading_changes_gradually_with_no_jump_into_swimming(seed):
    from ocean.drawingfish import ENTRY_LEVELLING, TURN_RATE, WANDER

    np.random.seed(seed)
    fish = DrawingFish(texid=1)
    hold_effort(fish, 1.0)
    headings = [heading(fish)]
    for _ in range(fish._init_animation_step + 30):
        fish.animation()
        headings.append(heading(fish))
    steps = [abs((b - a + np.pi) % (2 * np.pi) - np.pi) for a, b in zip(headings[:-1], headings[1:], strict=True)]
    assert max(steps) <= max(ENTRY_LEVELLING, TURN_RATE) + WANDER + 1e-9
    assert fish._animation_stage == "swim"


@pytest.mark.parametrize("seed", [3, 5])  # Enter from the top and the bottom
def test_vertical_entry_arrives_level_and_facing_its_way(seed):
    np.random.seed(seed)
    fish = DrawingFish(texid=1)
    assert abs(fish.vector[0]) > 0  # Never dead vertical
    hold_effort(fish, 1.0)
    for _ in range(fish._init_animation_step):
        fish.animation()
    assert abs(np.degrees(np.arctan2(abs(fish.vector[1]), abs(fish.vector[0])))) < 25  # Near level at hand-over
    faces_its_heading = 0.0 if (fish.vector[0] >= 0) == (fish._base_scale[0] >= 0) else 180.0
    assert fish.rotate[1] == faces_its_heading


def test_short_entry_keeps_easing_to_cruise_while_swimming():
    np.random.seed(0)
    fish = DrawingFish(texid=1)
    hold_effort(fish, 1.0)
    fish._water_resistance = 0.98
    fish._init_animation_step = 60  # Too short to slow all the way: 0.02 * 0.98^60 = 0.006
    for _ in range(60):
        fish.animation()
    assert fish._animation_stage == "swim" and speed_of(fish) > 1.5 * fish._cruise_speed
    for _ in range(120):
        fish.animation()
    assert np.isclose(speed_of(fish), fish._cruise_speed)


def test_exit_speeds_up_smoothly_to_double_pace():
    fish = swimming_fish_beyond([0.0, -0.2, 0.0], [0.003, 0.0, 0.0])
    cruise = speed_of(fish)
    speeds = [cruise]
    fish.go_away()
    speeds.append(speed_of(fish))
    for _ in range(120):
        fish.animation()
        speeds.append(speed_of(fish))
    ratios = [b / a for a, b in zip(speeds[:-1], speeds[1:], strict=True)]
    assert max(ratios) <= 1.1 and min(ratios) >= 1.0 - 1e-9, "exit speed must ramp, never snap"
    assert np.isclose(speeds[-1], 2 * cruise, rtol=0.02)
