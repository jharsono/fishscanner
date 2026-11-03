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
