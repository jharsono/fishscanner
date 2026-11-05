from pathlib import Path
from queue import Queue

import glfw
import numpy as np
import OpenGL.GL as gl

from engine.clock import FixedStepClock
from engine.drawing import Drawing
from engine.photos import PhotoWatcher
from engine.renderer import Renderer
from engine.shaders import ShaderProgram, compile_program
from engine.simplescanner import SimpleScanner
from main_server import FISH_LIMIT, PHOTOS_DIR, SERVER_PORT, STATE_FILE, load_fish_from_files
from ocean import IMAGES_DIR
from ocean.drawingfish import FISH_TRANSFORM, DrawingFish, prevent_depth_crossings
from ocean.drawingseaweed import SEAWEED_TRANSFORM, DrawingSeaweed
from ocean.drawingstatic import DrawingStatic
from ocean.roster import FishRoster, painted_extent
from remote.server import RemoteServer, create_app, lan_address

WINDOW_SIZE = (800, 600)
BACKGROUND_SCALE = (3.6, 2.0, 1.0)  # Background sprites cover this much of the world, centred on the origin
TICK_SECONDS = 1 / 60  # Animation step, 60 times per second


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
    Open the application window with an OpenGL 3.3 core profile context
    :return: glfw window handle
    """
    if not glfw.init():
        raise RuntimeError("Could not initialise glfw")
    glfw.window_hint(glfw.CONTEXT_VERSION_MAJOR, 3)
    glfw.window_hint(glfw.CONTEXT_VERSION_MINOR, 3)
    glfw.window_hint(glfw.OPENGL_PROFILE, glfw.OPENGL_CORE_PROFILE)
    glfw.window_hint(glfw.OPENGL_FORWARD_COMPAT, glfw.TRUE)  # Required by macOS for core profiles
    window = glfw.create_window(*WINDOW_SIZE, "FishScanner", None, None)
    if not window:
        glfw.terminate()
        raise RuntimeError("Could not create an OpenGL 3.3 window")
    glfw.make_context_current(window)
    glfw.swap_interval(1)  # Vertical sync
    return window


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
