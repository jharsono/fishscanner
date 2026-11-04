"""Smoke tests that render through the real OpenGL pipeline into a hidden window.

Skipped where no OpenGL 3.3 window can be created (headless CI).
"""

import warnings
from pathlib import Path
from queue import Queue

import numpy as np
import OpenGL.GL as gl
import pytest

import main_ocean
from engine.drawing import Drawing
from engine.renderer import Renderer
from engine.shaders import compile_program
from ocean.drawingfish import FISH_TRANSFORM
from ocean.drawingseaweed import SEAWEED_TRANSFORM
from ocean.drawingstatic import DrawingStatic

WIDTH, HEIGHT = main_ocean.WINDOW_SIZE


@pytest.fixture(scope="module")
def window():
    """The app's own window, hidden; skipped where no OpenGL 3.3 context can be created."""
    glfw = pytest.importorskip("glfw")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Headless Linux: glfw warns about the missing display before init() fails
        initialised = glfw.init()
    if not initialised:
        pytest.skip("glfw could not initialise")
    glfw.window_hint(glfw.VISIBLE, glfw.FALSE)
    try:
        handle = main_ocean.create_window()
    except RuntimeError as e:  # No OpenGL 3.3 context on this machine (headless CI)
        pytest.skip(str(e))
    yield handle
    Drawing.release_meshes()
    glfw.terminate()


@pytest.fixture
def renderer(window):
    glfw = pytest.importorskip("glfw")
    return Renderer(*glfw.get_framebuffer_size(window))


def read_pixel(x: int, y: int) -> tuple[int, ...]:
    data = gl.glReadPixels(x, y, 1, 1, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    assert isinstance(data, bytes)
    return tuple(int(value) for value in data)


def read_frame() -> np.ndarray:
    data = gl.glReadPixels(0, 0, WIDTH, HEIGHT, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE)
    assert isinstance(data, bytes)
    return np.frombuffer(data, dtype=np.uint8).reshape(HEIGHT, WIDTH, 4)


def solid_texture(rgba: tuple[int, int, int, int]) -> int:
    return Renderer.create_texture(np.full((2, 2, 4), rgba, dtype=np.uint8))


def full_screen_sprite(texture: int) -> DrawingStatic:
    sprite = DrawingStatic(texture)
    sprite.scale = np.array([3.6, 2.0, 1.0])
    return sprite


def test_sprite_covers_the_view(renderer):
    renderer.render([full_screen_sprite(solid_texture((255, 0, 0, 255)))])
    assert read_pixel(WIDTH // 2, HEIGHT // 2) == (255, 0, 0, 255)
    assert read_pixel(1, 1) == (255, 0, 0, 255)


def test_sprite_color_tints_texture(renderer):
    sprite = full_screen_sprite(solid_texture((255, 255, 255, 255)))
    sprite.color = np.array([0.0, 1.0, 0.0])
    renderer.render([sprite])
    assert read_pixel(WIDTH // 2, HEIGHT // 2) == (0, 255, 0, 255)


def test_transparent_texels_are_discarded(renderer):
    renderer.render([full_screen_sprite(solid_texture((255, 0, 0, 0)))])
    r, g, b, _ = read_pixel(WIDTH // 2, HEIGHT // 2)
    assert (r, g, b) == (26, 26, 51)  # The clear colour (0.1, 0.1, 0.2)


def test_nearer_sprite_wins_depth(renderer):
    back = full_screen_sprite(solid_texture((255, 0, 0, 255)))
    back.position = np.array([0.0, 0.0, -0.8])
    front = full_screen_sprite(solid_texture((0, 0, 255, 255)))
    front.position = np.array([0.0, 0.0, 0.5])
    renderer.render([front, back])
    assert read_pixel(WIDTH // 2, HEIGHT // 2) == (0, 0, 255, 255)


def test_smaller_y_is_higher_on_screen(renderer):
    sprite = DrawingStatic(solid_texture((255, 0, 0, 255)))
    sprite.position = np.array([0.0, -0.5, 0.0])  # Upper half in world space
    sprite.scale = np.array([3.6, 1.0, 1.0])
    renderer.render([sprite])
    assert read_pixel(WIDTH // 2, HEIGHT - 2)[:3] == (255, 0, 0)  # GL rows start at the bottom
    assert read_pixel(WIDTH // 2, 2)[:3] != (255, 0, 0)


@pytest.mark.parametrize("transform", [FISH_TRANSFORM, SEAWEED_TRANSFORM])
def test_sprite_shaders_compile_and_render(renderer, transform):
    shader = compile_program(transform)
    sprite = full_screen_sprite(solid_texture((0, 255, 0, 255)))
    sprite._shader = shader
    renderer.render([sprite])
    assert read_pixel(WIDTH // 2, HEIGHT // 2) == (0, 255, 0, 255)
    gl.glDeleteProgram(shader.id)


def test_scene_switching_does_not_accumulate_textures(renderer):
    resources = main_ocean.Resources()
    scene = main_ocean.Scene(resources)
    for _ in range(len(scene.backgrounds)):
        scene.switch_background(1)
    after_one_cycle = resources.texture_count
    for _ in range(3 * len(scene.backgrounds)):
        scene.switch_background(1)
        renderer.render(scene.drawings)
    assert resources.texture_count == after_one_cycle
    resources.release()


def fish_scan() -> np.ndarray:
    scan = np.zeros((600, 800, 4), dtype=np.uint8)
    scan[200:400, 200:600] = (255, 128, 0, 255)
    return scan


def test_scene_follows_the_enabled_fish(renderer):
    from ocean.drawingfish import DrawingFish

    resources = main_ocean.Resources()
    scene = main_ocean.Scene(resources)
    scene.scans = {"a.jpg": fish_scan(), "b.jpg": fish_scan()}
    scene.follow(["a.jpg", "b.jpg", "c.jpg"])  # No scan for c.jpg yet, so it waits
    assert set(scene.swimming) == {"a.jpg", "b.jpg"}
    leaving = scene.swimming["a.jpg"]
    scene.follow(["b.jpg"])
    assert set(scene.swimming) == {"b.jpg"}
    assert leaving._animation_stage == "finish"  # Swims off rather than vanishing
    assert leaving in scene.drawings
    scene.follow(["b.jpg", "a.jpg"])
    assert scene.swimming["a.jpg"] is not leaving  # A fresh fish swims in while the old one leaves
    assert sum(isinstance(d, DrawingFish) for d in scene.drawings) == 3
    resources.release()


def test_step_registers_every_queued_scan_and_adds_only_the_enabled_fish(renderer, tmp_path: Path):
    from ocean.roster import FishRoster

    resources = main_ocean.Resources()
    scene = main_ocean.Scene(resources)
    roster = FishRoster(tmp_path / "tank.json", default_cap=2)
    queue: Queue = Queue()
    for name in ["a.jpg", "b.jpg", "c.jpg"]:
        queue.put((tmp_path / name, fish_scan()))
    main_ocean.step(renderer, scene, queue, roster)
    assert queue.empty()
    assert set(scene.scans) == {"a.jpg", "b.jpg", "c.jpg"}  # Kept, so a disabled fish can come back
    assert set(scene.swimming) == {"b.jpg", "c.jpg"}  # The cap disabled the oldest before it swam in
    roster.set_enabled("a.jpg", True)
    main_ocean.step(renderer, scene, queue, roster)
    assert set(scene.swimming) == {"c.jpg", "a.jpg"}
    resources.release()


def test_a_dead_fish_releases_its_texture(renderer):
    resources = main_ocean.Resources()
    scene = main_ocean.Scene(resources)
    scene.scans = {"a.jpg": fish_scan()}
    before = resources.texture_count
    scene.follow(["a.jpg"])
    leaving = scene.swimming["a.jpg"]
    scene.follow([])
    leaving.is_alive = False
    scene.remove_dead_fish()
    assert leaving not in scene.drawings
    assert resources.texture_count == before
    resources.release()


def to_clip(renderer, x: float, y: float) -> np.ndarray:
    return renderer.projection @ np.array([x, y, 0.0, 1.0], dtype=np.float32)


def test_resize_updates_viewport_and_projection(renderer):
    renderer.resize(1600, 600)
    assert tuple(gl.glGetIntegerv(gl.GL_VIEWPORT)) == (0, 0, 1600, 600)
    aspect = 1600 / 600
    assert np.isclose(to_clip(renderer, aspect, 0.0)[0], 1.0)  # Wider world, right edge on the window edge
    assert np.isclose(to_clip(renderer, 0.0, 1.0)[1], -1.0)  # Full height still visible (world y points down)
    renderer.resize(WIDTH, HEIGHT)


def test_wide_window_crops_height_beyond_max_aspect(window):
    glfw = pytest.importorskip("glfw")
    renderer = Renderer(*glfw.get_framebuffer_size(window), max_aspect=1.8)
    renderer.resize(1600, 600)  # Aspect 2.67, wider than the backgrounds
    assert np.isclose(to_clip(renderer, 1.8, 0.0)[0], 1.0)  # Background edge lands on the window edge
    assert np.isclose(to_clip(renderer, 0.0, 1.8 / (1600 / 600))[1], -1.0)  # Only the middle band of height is shown
    renderer.resize(800, 600)  # Aspect 1.33 is under the limit: unchanged behaviour
    assert np.isclose(to_clip(renderer, 800 / 600, 1.0)[0], 1.0)
    assert np.isclose(to_clip(renderer, 0.0, 1.0)[1], -1.0)


def test_bubbles_attached_to_a_fish_are_drawn(renderer):
    from ocean import IMAGES_DIR
    from ocean.drawingbubble import DrawingBubble
    from ocean.drawingfish import DrawingFish

    fish = DrawingFish(solid_texture((255, 0, 0, 255)))
    fish.position = np.array([-1.0, 0.8, 0.0])  # Out of the way, bottom left
    fish.scale = np.array([0.1, 0.1, 1.0])
    renderer.render([fish])
    without_bubble = read_frame()

    bubble = DrawingBubble(Renderer.create_texture_from_file(IMAGES_DIR / "bubble.png"), start_x=0.0, start_y=0.0)
    bubble.scale = np.array([0.5, 0.5, 1.0])
    fish._bubbles.append(bubble)
    renderer.render([fish])
    changed = (read_frame() != without_bubble).any(axis=2)
    assert changed.sum() > 1000, "the bubble left no visible pixels"


def test_near_fish_is_drawn_in_front_of_far_fish(renderer):
    from ocean.drawingfish import DrawingFish

    near = DrawingFish(solid_texture((255, 0, 0, 255)))
    far = DrawingFish(solid_texture((0, 0, 255, 255)))
    for fish in (near, far):
        fish.position = np.array([0.0, 0.0, 0.0])
        fish.scale = np.array([1.0, 0.75, 0.3])
    far.position[2] = -0.5
    for order in ([near, far], [far, near]):
        renderer.render(order)
        assert read_pixel(WIDTH // 2, HEIGHT // 2)[:3] == (255, 0, 0), f"far fish drawn on top with order {order}"


def silhouette_box(frame: np.ndarray, clear: tuple[int, int, int]) -> tuple[int, int, int, int]:
    """Bounding box (x0, x1, y0, y1) of pixels that differ from the clear colour."""
    mask = (frame[..., :3] != np.array(clear, dtype=np.uint8)).any(axis=2)
    ys, xs = np.nonzero(mask)
    return int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())


def test_fish_tail_beat_foreshortens_width_but_never_moves_height(renderer):
    from ocean.drawingfish import FISH_TRANSFORM, DrawingFish

    shader = compile_program(FISH_TRANSFORM)
    fish = DrawingFish(solid_texture((255, 0, 0, 255)), shader=shader)
    fish.position = np.array([0.0, 0.0, 0.0])
    fish.scale = np.array([1.0, 0.5, 1.0])
    fish._speed_factor = 0.0
    clear = (26, 26, 51)
    boxes = []
    fish.shader_params[1] = 0.6  # Peak swing
    for phase in np.linspace(0.0, 2 * np.pi, 7):  # One beat
        fish.shader_params[0] = phase
        renderer.render([fish])
        boxes.append(silhouette_box(read_frame(), clear))
    heights = {y1 - y0 for _, _, y0, y1 in boxes}
    widths = {x1 - x0 for x0, x1, _, _ in boxes}
    assert len(heights) == 1, f"the beat must not move the fish vertically: {heights}"
    assert len(widths) > 1, "the tail must foreshorten over the beat"
    gl.glDeleteProgram(shader.id)


def test_head_turn_foreshortens_the_head_end_only(renderer):
    from ocean.drawingfish import FISH_TRANSFORM, DrawingFish

    shader = compile_program(FISH_TRANSFORM)
    fish = DrawingFish(solid_texture((255, 0, 0, 255)), shader=shader)
    fish.position = np.array([0.0, 0.0, 0.0])
    fish.scale = np.array([1.0, 0.5, 1.0])
    fish._speed_factor = 0.0
    clear = (26, 26, 51)
    fish.shader_params[:] = (0.0, 0.0, 0.0, 0.0)
    renderer.render([fish])
    x0, x1, y0, y1 = silhouette_box(read_frame(), clear)
    fish.shader_params[2] = 0.5  # Head turned
    renderer.render([fish])
    tx0, tx1, ty0, ty1 = silhouette_box(read_frame(), clear)
    assert (ty0, ty1) == (y0, y1)  # Never vertical
    assert tx0 == x0  # The tail end (-x, left on screen) does not move
    assert tx1 < x1  # The head end pulls in
    gl.glDeleteProgram(shader.id)
