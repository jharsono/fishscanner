import warnings
from pathlib import Path
from queue import Queue

import glfw
import numpy as np
import OpenGL.GL as gl

from engine.clock import FixedStepClock
from engine.drawing import Drawing
from engine.photos import PhotoWatcher, list_photos, scan_photo_file
from engine.renderer import Renderer
from engine.shaders import ShaderProgram, compile_program
from engine.simplescanner import SimpleScanner
from ocean import IMAGES_DIR
from ocean.drawingfish import FISH_TRANSFORM, DrawingFish, prevent_depth_crossings
from ocean.drawingseaweed import SEAWEED_TRANSFORM, DrawingSeaweed
from ocean.drawingstatic import DrawingStatic
from ocean.roster import FishRoster
from remote.server import RemoteServer, create_app, lan_address

PHOTOS_DIR = Path("photos")
STATE_FILE = PHOTOS_DIR / "tank.json"  # The fish cap and the disabled photos, kept across restarts
SERVER_PORT = 8080  # Remote control page, opened from a phone on the same network
WINDOW_SIZE = (800, 600)
BACKGROUND_SCALE = (3.6, 2.0, 1.0)  # Background sprites cover this much of the world, centred on the origin
TICK_SECONDS = 1 / 60  # Animation step, 60 times per second
FISH_LIMIT = 10  # Default cap on fish in the tank; the remote control can change it
# OpenGL contexts to try, best first. glfw keeps window hints between windows, so each attempt
# sets every context hint it depends on (the profile hints are ignored for OpenGL ES).
CONTEXTS = [
    (
        "OpenGL 3.3 core",
        {
            glfw.CLIENT_API: glfw.OPENGL_API,
            glfw.CONTEXT_VERSION_MAJOR: 3,
            glfw.CONTEXT_VERSION_MINOR: 3,
            glfw.OPENGL_PROFILE: glfw.OPENGL_CORE_PROFILE,
            glfw.OPENGL_FORWARD_COMPAT: glfw.TRUE,  # Required by macOS for core profiles
        },
    ),
    (
        "OpenGL ES 2.0",  # All the Raspberry Pi 3B's GPU offers besides desktop OpenGL 2.1
        {
            glfw.CLIENT_API: glfw.OPENGL_ES_API,
            glfw.CONTEXT_VERSION_MAJOR: 2,
            glfw.CONTEXT_VERSION_MINOR: 0,
        },
    ),
]


class Resources:
    """GPU handles created by the app, deleted together before the context goes away."""

    def __init__(self):
        self._textures: list[int] = []
        self._programs: list[int] = []

    def texture(self, texid: int) -> int:
        self._textures.append(texid)
        return texid

    def program(self, shader: ShaderProgram) -> ShaderProgram:
        self._programs.append(shader.id)
        return shader

    @property
    def texture_count(self) -> int:
        return len(self._textures)

    def release_texture(self, texid: int) -> None:
        self._textures.remove(texid)
        gl.glDeleteTextures(1, [texid])

    def release(self) -> None:
        if self._textures:
            gl.glDeleteTextures(len(self._textures), self._textures)
        for program in self._programs:
            gl.glDeleteProgram(program)
        self._textures.clear()
        self._programs.clear()


class Scene:
    """Everything that is drawn plus the handles needed to build and rebuild it."""

    def __init__(self, resources: Resources):
        self.resources = resources
        self.drawings: list[Drawing] = []
        self._file_textures: dict[Path, int] = {}  # Decoration textures, uploaded once and reused across scene switches
        self.seaweed_shader = resources.program(compile_program(SEAWEED_TRANSFORM))
        self.fish_shader = resources.program(compile_program(FISH_TRANSFORM))
        self.bubble_texture = self.load_texture("bubble.png")
        self.backgrounds = [
            {"type": "complex", "name": "Ocean"},
            {"type": "simple", "name": "Scene 2", "background": "scene2.jpg"},
            {"type": "simple", "name": "Scene 3", "background": "scene3.webp"},
        ]
        self.background_index = 0
        self.scans: dict[str, np.ndarray] = {}  # Every scanned photo by file name, so a disabled fish can come back
        self.swimming: dict[str, DrawingFish] = {}  # Fish in the tank by photo name; leaving fish are not here
        self.update_background()

    def load_texture(self, name: str | Path) -> int:
        path = IMAGES_DIR / name
        if path not in self._file_textures:
            self._file_textures[path] = self.resources.texture(Renderer.create_texture_from_file(path))
        return self._file_textures[path]

    def switch_background(self, step: int) -> None:
        self.background_index = (self.background_index + step) % len(self.backgrounds)
        self.update_background()

    def update_background(self) -> None:
        """
        Rebuild the decorative sprites for the current background, keeping the fish
        :return:
        """
        self.drawings[:] = [d for d in self.drawings if isinstance(d, DrawingFish)]
        config = self.backgrounds[self.background_index]
        if config["type"] == "complex":
            self.draw_complex_ocean()
        else:  # simple scene
            self.drawings.append(self.create_back_layer(config["background"], -0.8))

    def create_back_layer(self, filename: str, z: float) -> DrawingStatic:
        """
        Create sprite for the scene background
        :param filename: Background image name in IMAGES_DIR
        :param z: Depth position of the sprite
        :return: Sprite object for the background
        """
        drawing_back = DrawingStatic(self.load_texture(filename))
        drawing_back.position = np.array([0, 0.0, z])
        drawing_back.scale = np.array(BACKGROUND_SCALE)
        return drawing_back

    def add_seaweed(
        self, texture: int, position: list[float], scale: list[float], color: list[float] | None = None
    ) -> None:
        drawing = DrawingSeaweed(texture, shader=self.seaweed_shader)
        drawing.position = np.array(position)
        drawing.scale = np.array(scale)
        if color is not None:
            drawing.color = np.array(color)
        self.drawings.append(drawing)

    def draw_sails(self) -> None:
        """
        Support function to draw sails
        :return:
        """
        self.add_seaweed(self.load_texture("sail_1.png"), [1.2, -0.43, -0.77], [0.6, 0.4, 1.0])
        self.add_seaweed(self.load_texture("sail_2.png"), [1.6, -0.34, -0.77], [0.3, 0.5, 1.0])
        self.add_seaweed(self.load_texture("sail_3.png"), [1.7, -0.71, -0.77], [0.2, 0.3, 1.0])

    def draw_complex_ocean(self) -> None:
        """
        Draw the complex ocean scene with all decorative elements
        :return:
        """
        for image in ["back_down.png", "back_middle.png", "back_reef.png"]:
            self.drawings.append(self.create_back_layer(image, -0.8))

        self.draw_sails()

        for image in ["seaweed_2.png", "seaweed_1.png", "seaweed_3.png"]:
            texture = self.load_texture(image)
            # Draw seaweed under the ship
            self.add_seaweed(texture, [1.2, 0.4, -0.75], [0.8, 0.4, 1.0])
            # Draw seaweed in the right corner
            self.add_seaweed(texture, [1.2, 1.0, 0.9], [0.8, 1.4, 1.0])
            # Draw seaweed in the front of the rock
            self.add_seaweed(texture, [0.2, 0.15, -0.7], [0.4, 0.4, 1.0])
            # Draw seaweed in the left corner
            self.add_seaweed(texture, [-1.2, 0.6, 0.9], [0.3, 1.0, 1.0])
            # Draw seaweed on the background
            self.add_seaweed(texture, [-0.8, -0.8, -0.795], [0.3, 1.2, 1.0], color=[0.3, 0.3, 0.8])
            self.add_seaweed(texture, [0.0, -0.2, -0.795], [-0.3, 1.0, 1.0])
            self.add_seaweed(texture, [-0.4, -0.2, -0.795], [0.1, 0.3, 1.0])

    def add_fish(self, name: str) -> None:
        scanned_fish = self.scans[name]
        texture = self.resources.texture(Renderer.create_texture(scanned_fish))
        fish = DrawingFish(
            texture, shader=self.fish_shader, bubble_texture_id=self.bubble_texture, extent=painted_extent(scanned_fish)
        )
        self.drawings.append(fish)
        self.swimming[name] = fish

    def follow(self, enabled: list[str]) -> None:
        """
        Send away the fish that are no longer enabled and add enabled fish that are not in the tank yet
        :param enabled: Photo names of the enabled fish; a name whose scan has not arrived yet waits
        :return:
        """
        wanted = set(enabled)
        for name in [name for name in self.swimming if name not in wanted]:
            self.swimming.pop(name).go_away()
        for name in enabled:
            if name not in self.swimming and name in self.scans:
                self.add_fish(name)

    def remove_dead_fish(self) -> None:
        dead = [d for d in self.drawings if isinstance(d, DrawingFish) and not d.is_alive]
        self.drawings[:] = [d for d in self.drawings if d not in dead]
        for fish in dead:
            self.resources.release_texture(fish.texid)


def painted_extent(scanned_fish: np.ndarray) -> tuple[float, float]:
    """
    Smallest box centred on the canvas that contains a scan's opaque pixels, as fractions of
    the canvas per axis. The scanner keeps the drawing wherever it sits on the page, so the
    box reaches out to the farthest painted pixel on each axis rather than hugging the paint.
    :param scanned_fish: RGBA scan
    :return: (width fraction, height fraction), 1.0 when nothing is opaque
    """
    rows, cols = np.nonzero(scanned_fish[..., 3])
    if rows.size == 0:
        return (1.0, 1.0)
    height, width = scanned_fish.shape[:2]
    reach_x = max(0.5 - cols.min() / width, (cols.max() + 1) / width - 0.5)
    reach_y = max(0.5 - rows.min() / height, (rows.max() + 1) / height - 0.5)
    return (min(2 * reach_x, 1.0), min(2 * reach_y, 1.0))


def load_fish_from_files(scanner: SimpleScanner, scanned_fish_queue: Queue) -> int:
    """
    Scan every photo already in the photos folder
    :param scanner: Object of scanner to process photos
    :param scanned_fish_queue: Queue of (path, RGBA scan) the animation loop turns into fish sprites
    :return: Number of fish found
    """
    found = 0
    for path in list_photos(PHOTOS_DIR):
        scanned_fish = scan_photo_file(path, scanner)
        if scanned_fish is not None:
            scanned_fish_queue.put((path, scanned_fish))
            found += 1
    return found


def step(renderer: Renderer, scene: Scene, scanned_fish_queue: Queue, roster: FishRoster) -> None:
    """
    One animation tick: move sprites, register new scans, bring the tank in line with the enabled fish,
    retire dead ones
    :param renderer: Object of the Engine to animate all the objects
    :param scene: Scene holding the sprites
    :param scanned_fish_queue: Queue of (path, RGBA scan) scanning results
    :param roster: Which fish are enabled
    :return:
    """
    prevent_depth_crossings([d for d in scene.drawings if isinstance(d, DrawingFish)])
    renderer.animate(scene.drawings)
    # Register every waiting scan before following, so a fish the cap disables never swims in
    while not scanned_fish_queue.empty():
        path, scanned_fish = scanned_fish_queue.get()
        scene.scans[path.name] = scanned_fish
        roster.register(path.name, scanned_fish)
    scene.follow(roster.enabled())
    scene.remove_dead_fish()


def create_window():
    """
    Open the application window with the first context in CONTEXTS that the machine offers
    :return: glfw window handle
    """
    if not glfw.init():
        raise RuntimeError("Could not initialise glfw")
    window = None
    failures = []
    for name, hints in CONTEXTS:
        for hint, value in hints.items():
            glfw.window_hint(hint, value)
        # glfw reports a context the machine lacks as a warning, not an error: keep it for the message
        with warnings.catch_warnings(record=True) as reasons:
            warnings.simplefilter("always", glfw.GLFWError)
            window = glfw.create_window(*WINDOW_SIZE, "FishScanner", None, None)
        if window:
            break
        failures.append(f"{name}: {'; '.join(str(reason.message) for reason in reasons) or 'no reason given'}")
    if not window:
        glfw.terminate()
        raise RuntimeError("Could not create an OpenGL window. " + " | ".join(failures))
    glfw.make_context_current(window)
    glfw.swap_interval(1)  # Vertical sync
    return window


def toggle_fullscreen(window):
    """
    Switch between filling the primary monitor and a WINDOW_SIZE window centred on the monitor.
    The window's earlier position is not restored: Wayland cannot report it.
    :param window: glfw window handle
    """
    monitor = glfw.get_window_monitor(window)
    if not monitor:
        monitor = glfw.get_primary_monitor()
        mode = glfw.get_video_mode(monitor)
        glfw.set_window_monitor(window, monitor, 0, 0, mode.size.width, mode.size.height, mode.refresh_rate)
        return
    mode = glfw.get_video_mode(monitor)
    monitor_x, monitor_y = glfw.get_monitor_pos(monitor)
    width, height = WINDOW_SIZE
    x, y = monitor_x + (mode.size.width - width) // 2, monitor_y + (mode.size.height - height) // 2
    # No monitor means windowed, as glfw documents; pyGLFW's stub does not allow None
    glfw.set_window_monitor(window, None, x, y, width, height, 0)  # pyright: ignore[reportArgumentType]


def main():
    window = create_window()
    renderer = Renderer(*glfw.get_framebuffer_size(window), max_aspect=BACKGROUND_SCALE[0] / BACKGROUND_SCALE[1])
    resources = Resources()
    resources.program(renderer.default_shader)
    scene = Scene(resources)

    scanner = SimpleScanner()
    scanned_fish_queue: Queue = Queue()
    PHOTOS_DIR.mkdir(exist_ok=True)
    roster = FishRoster(STATE_FILE, default_cap=FISH_LIMIT)
    found = load_fish_from_files(scanner, scanned_fish_queue)
    print(f"Loaded {found} fish from {PHOTOS_DIR.resolve()}; drop photos there to add more")

    # Scan photos added while the app is running. A photo that lands between the startup
    # scan above and this start() is treated as already present and will not be scanned.
    watcher = PhotoWatcher(PHOTOS_DIR, scanner, scanned_fish_queue)
    watcher.start()

    # Uploads land in PHOTOS_DIR, where the watcher picks them up like any other new photo
    server = RemoteServer(create_app(roster, PHOTOS_DIR), port=SERVER_PORT)
    try:
        server.start()
    except OSError as e:  # The port is taken: the tank still runs, without the remote control
        print(f"Remote control unavailable, cannot listen on port {SERVER_PORT}: {e}")
    else:
        print(f"Remote control: http://{lan_address()}:{SERVER_PORT}")

    def on_key(window, key, scancode, action, mods):
        if action != glfw.PRESS:
            return
        if key == glfw.KEY_ESCAPE:
            glfw.set_window_should_close(window, True)
        elif key == glfw.KEY_LEFT:
            scene.switch_background(-1)
        elif key == glfw.KEY_RIGHT:
            scene.switch_background(1)
        elif key == glfw.KEY_F:
            toggle_fullscreen(window)

    glfw.set_key_callback(window, on_key)
    glfw.set_framebuffer_size_callback(window, lambda _window, width, height: renderer.resize(width, height))

    # Fixed-step animation: ticks happen at 60 Hz regardless of the display rate
    clock = FixedStepClock(TICK_SECONDS)
    last_time = glfw.get_time()
    while not glfw.window_should_close(window):
        now = glfw.get_time()
        for _ in range(clock.advance(now - last_time)):
            step(renderer, scene, scanned_fish_queue, roster)
        last_time = now
        renderer.render(scene.drawings)
        glfw.swap_buffers(window)
        glfw.poll_events()

    server.stop()
    watcher.stop()
    resources.release()
    Drawing.release_meshes()
    glfw.terminate()


if __name__ == "__main__":
    main()
