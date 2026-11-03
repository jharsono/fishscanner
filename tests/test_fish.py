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
    fish.animation()
    assert np.isclose(abs((fish.position - before)[0]), abs(fish.vector[0]))


def count_direction_changes(fish: DrawingFish, axis: int, ticks: int) -> int:
    changes = 0
    last = np.sign(fish.vector[axis])
    for _ in range(ticks):
        fish.animation()
        if np.sign(fish.vector[axis]) != last:
            changes += 1
            last = np.sign(fish.vector[axis])
    return changes


def swimming_fish_beyond(position: list[float], vector: list[float]) -> DrawingFish:
    """A fish already past a border and still heading out, as a long entry animation can leave it."""
    fish = DrawingFish(texid=1)
    start_swimming(fish)
    fish._depth_period = 10**6  # Keep full speed for a clear count
    fish.position = np.array(position)
    fish.vector = np.array(vector)
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
    if axis == 0:
        assert fish.rotate[1] == 180 and fish.rotation_vector[1] == 0  # Turned around exactly once
    else:
        assert fish.rotate[1] == 0 and fish.rotation_vector[1] == 0  # A vertical bounce never turns the fish


def test_fish_beyond_a_corner_turns_once_on_each_axis():
    fish = swimming_fish_beyond([2.0, 0.6, 0.0], [0.003, 0.002, 0.0])
    x_changes = 0
    y_changes = 0
    last = np.sign(fish.vector[:2])
    for _ in range(600):
        fish.animation()
        now = np.sign(fish.vector[:2])
        x_changes += now[0] != last[0]
        y_changes += now[1] != last[1]
        last = now
    assert (x_changes, y_changes) == (1, 1)
    assert fish.rotate[1] == 180 and fish.rotation_vector[1] == 0
