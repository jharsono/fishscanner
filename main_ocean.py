import os
import time
from collections.abc import Callable
from functools import partial
from glob import glob
from queue import Queue
from threading import Thread

import cv2
import numpy as np
import OpenGL.GL as gl
import OpenGL.GLUT as glut
from PIL import Image
from pillow_heif import register_heif_opener
from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from engine.drawing import Drawing
from engine.renderer import Renderer
from engine.simplescanner import SimpleScanner
from ocean.drawingfish import FISH_SHADER_CODE, DrawingFish
from ocean.drawingseaweed import SEAWEED_SHADER_CODE, DrawingSeaweed
from ocean.drawingstatic import DrawingStatic

# Register HEIF opener for HEIC support
register_heif_opener()


def create_back_layer(
    filename: str,
    z: float,
    shader: int = 0,
) -> DrawingStatic:
    """
    Create sprite for the scene background
    :param filename: Path to the background image
    :param z: Depth position of the sprite
    :param shader: Shader ID for the background
    :return: Sprite object for the background
    """
    drawing_back = DrawingStatic(Renderer.create_texture_from_file(filename), shader=shader)
    drawing_back.position = np.array([0, 0.0, z])
    drawing_back.scale = np.array([3.6, 2.0, 1.0])
    return drawing_back


def draw_sails(
    drawings_list: list[Drawing],
    shader: int,
) -> None:
    """
    Support function to draw sails
    :param drawings_list: List of sprites to draw
    :param shader: Shader to animate the sails
    :return:
    """
    drawing = DrawingSeaweed(Renderer.create_texture_from_file("ocean/images/sail_1.png"), shader=shader)
    drawing.position = np.array([1.2, -0.43, -0.77])
    drawing.scale = np.array([0.6, 0.4, 1.0])
    drawings_list.append(drawing)

    drawing = DrawingSeaweed(Renderer.create_texture_from_file("ocean/images/sail_2.png"), shader=shader)
    drawing.position = np.array([1.6, -0.34, -0.77])
    drawing.scale = np.array([0.3, 0.5, 1.0])
    drawings_list.append(drawing)

    drawing = DrawingSeaweed(Renderer.create_texture_from_file("ocean/images/sail_3.png"), shader=shader)
    drawing.position = np.array([1.7, -0.71, -0.77])
    drawing.scale = np.array([0.2, 0.3, 1.0])
    drawings_list.append(drawing)


def draw_complex_ocean(drawings_list: list[Drawing]) -> None:
    """
    Draw the complex ocean scene with all decorative elements
    :param drawings_list: Lists of sprites to draw
    :return:
    """
    seaweed_shader_program = Renderer.create_shader(gl.GL_VERTEX_SHADER, SEAWEED_SHADER_CODE)
    cleanup_and_exit.seaweed_shader = seaweed_shader_program
    cleanup_and_exit.seaweed_textures = []
    cleanup_and_exit.background_textures = []

    # Create and store background textures
    for image in ["back_down.png", "back_middle.png", "back_reef.png"]:
        texture = Renderer.create_texture_from_file(f"ocean/images/{image}")
        cleanup_and_exit.background_textures.append(texture)
        drawings_list.append(create_back_layer(f"ocean/images/{image}", -0.8))

    draw_sails(drawings_list, seaweed_shader_program)

    # Create and store seaweed textures
    seaweed_images = ["seaweed_2.png", "seaweed_1.png", "seaweed_3.png"]
    for image in seaweed_images:
        texture = Renderer.create_texture_from_file(f"ocean/images/{image}")
        cleanup_and_exit.seaweed_textures.append(texture)

        seaweed_texture = texture
        # Draw seaweed under the ship
        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([1.2, 0.4, -0.75])
        drawing.scale = np.array([0.8, 0.4, 1.0])
        drawings_list.append(drawing)

        seaweed_texture = texture
        # Draw seaweed in the right corner
        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([1.2, 1.0, 0.9])
        drawing.scale = np.array([0.8, 1.4, 1.0])
        drawings_list.append(drawing)

        # Draw seaweed in the front of the rock
        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([0.2, 0.15, -0.7])
        drawing.scale = np.array([0.4, 0.4, 1.0])
        drawings_list.append(drawing)

        seaweed_texture = texture
        # Draw seaweed in the left corner
        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([-1.2, 0.6, 0.9])
        drawing.scale = np.array([0.3, 1.0, 1.0])
        drawings_list.append(drawing)

        # Draw seaweed on the background
        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([-0.8, -0.8, -0.795])
        drawing.scale = np.array([0.3, 1.2, 1.0])
        drawing.color = np.array([0.3, 0.3, 0.8])
        drawings_list.append(drawing)

        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([0.0, -0.2, -0.795])
        drawing.scale = np.array([-0.3, 1.0, 1.0])
        drawings_list.append(drawing)

        drawing = DrawingSeaweed(seaweed_texture, shader=seaweed_shader_program)
        drawing.position = np.array([-0.4, -0.2, -0.795])
        drawing.scale = np.array([0.1, 0.3, 1.0])
        drawings_list.append(drawing)


def draw_simple_scene(drawings_list: list[Drawing], image_path: str) -> None:
    """
    Draw a simple scene with just a background image
    :param drawings_list: Lists of sprites to draw
    :param image_path: Path to the background image
    :return:
    """
    cleanup_and_exit.background_textures = []
    texture = Renderer.create_texture_from_file(image_path)
    cleanup_and_exit.background_textures.append(texture)
    drawings_list.append(create_back_layer(image_path, -0.8))


def update_scene(drawings_list: list[Drawing], scene_config: dict) -> None:
    """
    Update the scene based on the scene configuration
    :param drawings_list: List of sprites to draw
    :param scene_config: Dictionary containing scene configuration
    """
    # Keep track of fish
    fish_drawings = [d for d in drawings_list if isinstance(d, DrawingFish)]

    # Remove everything except fish
    drawings_list[:] = fish_drawings

    # Draw the new scene based on its type
    if scene_config["type"] == "complex":
        draw_complex_ocean(drawings_list)
    else:  # simple scene
        draw_simple_scene(drawings_list, scene_config["background"])


def scan_from_frame(
    frame: np.ndarray,
    scanner: SimpleScanner,
) -> np.ndarray | None:
    """
    Process a fish from an image file
    :param frame: BGR photo of the fish drawing
    :param scanner: Object of scanner to process photo
    :return: Processed frame with a fish selected from the background
    """
    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    try:
        processed_frame = scanner.scan(frame)
    except ValueError as e:
        print(e)
        return None
    processed_frame = scanner.remove_background(processed_frame)
    return processed_frame


def load_fish_from_files(
    scanner: SimpleScanner,
    drawings_list: list[Drawing],
    fish_queue: Queue,
    fish_shader_program: int = 0,
    bubble_texture: int = 0,
) -> None:
    """
    Load all the predrawing fish from the folder
    :param scanner: Object of scanner to process photos
    :param drawings_list: Lists of sprites to add fish in it
    :param fish_queue: Queue to maintain order of fish
    :param fish_shader_program: ID of fish shader
    :param bubble_texture: ID of bubble texture
    :return:
    """
    # Load both JPG and HEIC files
    jpg_files = glob("./photos/*.jpg")
    heic_files = glob("./photos/*.heic")
    files = jpg_files + heic_files

    for filename in files:
        try:
            if filename.lower().endswith(".heic"):
                heif_file = Image.open(filename)
                rgb_image = heif_file.convert("RGB")
                frame = cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2BGR)
            else:
                frame = cv2.imread(filename)

            if frame is None:
                print(f"Error reading image with filename: {filename}")
                continue

            scanned_fish = scan_from_frame(frame, scanner)
            if scanned_fish is not None:
                drawing = DrawingFish(
                    Renderer.create_texture(scanned_fish), shader=fish_shader_program, bubble_texture_id=bubble_texture
                )
                drawings_list.append(drawing)
                fish_queue.put(drawing)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")
            continue


class PhotoHandler(FileSystemEventHandler):
    def __init__(self, scanner: SimpleScanner, scanned_fish_queue: Queue):
        self.scanner = scanner
        self.scanned_fish_queue = scanned_fish_queue
        self.processed_files = set()

    def on_created(self, event):
        if not isinstance(event, FileCreatedEvent):
            return

        filename = os.fsdecode(event.src_path)
        if not (filename.lower().endswith(".jpg") or filename.lower().endswith(".heic")):
            return

        if filename in self.processed_files:
            return

        try:
            if filename.lower().endswith(".heic"):
                # Load HEIC files using pillow-heif
                heif_file = Image.open(filename)
                # Convert to RGB format that OpenCV expects
                rgb_image = heif_file.convert("RGB")
                # Convert PIL image to OpenCV format
                frame = cv2.cvtColor(np.array(rgb_image), cv2.COLOR_RGB2BGR)
            else:
                # Load JPG files using OpenCV directly
                frame = cv2.imread(filename)

            if frame is None:
                print(f"Error reading image with filename: {filename}")
                return

            scanned_fish = scan_from_frame(frame, self.scanner)
            if scanned_fish is not None:
                self.scanned_fish_queue.put(scanned_fish)
                self.processed_files.add(filename)
        except Exception as e:
            print(f"Error processing {filename}: {str(e)}")


def watch_photos_directory(
    scanner: SimpleScanner,
    scanned_fish_queue: Queue,
) -> None:
    """
    Watch the photos directory for new files using filesystem events
    :param scanner: Scanner object to process photos
    :param scanned_fish_queue: Queue to store scanned fish
    """
    event_handler = PhotoHandler(scanner, scanned_fish_queue)
    observer = Observer()
    observer.schedule(event_handler, path="./photos", recursive=False)
    observer.start()

    # Store observer in cleanup function for access during exit
    cleanup_and_exit.observer = observer

    try:
        while True:
            time.sleep(1)  # Keep thread alive
    except KeyboardInterrupt:
        observer.stop()
    observer.join()


def cleanup_and_exit():
    """
    Cleanup function to be called before program exit
    """
    # Stop the observer thread
    if hasattr(cleanup_and_exit, "observer"):
        cleanup_and_exit.observer.stop()
        cleanup_and_exit.observer.join()

    # Clean up OpenGL resources
    # Delete shaders
    if hasattr(cleanup_and_exit, "fish_shader"):
        gl.glDeleteProgram(cleanup_and_exit.fish_shader)
    if hasattr(cleanup_and_exit, "seaweed_shader"):
        gl.glDeleteProgram(cleanup_and_exit.seaweed_shader)

    # Delete textures
    textures_to_delete = []
    if hasattr(cleanup_and_exit, "bubble_texture"):
        textures_to_delete.append(cleanup_and_exit.bubble_texture)
    if hasattr(cleanup_and_exit, "seaweed_textures"):
        textures_to_delete.extend(cleanup_and_exit.seaweed_textures)
    if hasattr(cleanup_and_exit, "background_textures"):
        textures_to_delete.extend(cleanup_and_exit.background_textures)

    if textures_to_delete:
        gl.glDeleteTextures(textures_to_delete)

    # Clean up VBO buffers from drawings
    if hasattr(cleanup_and_exit, "drawings_list"):
        for drawing in cleanup_and_exit.drawings_list:
            if hasattr(drawing, "_vbo_vertices"):
                drawing._vbo_vertices.delete()
            if hasattr(drawing, "_vbo_texcoords"):
                drawing._vbo_texcoords.delete()

    # Close GLUT window
    window = glut.glutGetWindow()
    if window > 0:  # Only close if window exists
        glut.glutDestroyWindow(window)

    # Exit normally with success code
    os._exit(0)  # Use os._exit to avoid raising SystemExit exception


def create_key_processor(
    scanner: SimpleScanner,
    scanned_fish_queue: Queue,
    drawings_list: list[Drawing],
    background_scenes: list[dict],
    current_scene_index: list[int],
) -> tuple[Callable, Callable]:
    """
    Create function to process keyboard events
    :param scanner: Scanner object
    :param scanned_fish_queue: Queue to store scanned fish
    :param drawings_list: List of sprites to draw
    :param background_scenes: List of scene configurations
    :param current_scene_index: Mutable list to keep track of the current scene index
    :return: Tuple of keyboard and special key handlers
    """

    def process_key(key: bytes, *_):
        """
        Process regular keyboard events
        :param key: Pressed key
        :param _: Other parameters
        :return:
        """
        if key == b"\x1b":  # esc
            cleanup_and_exit()

    def process_special_key(key: int, *_):
        """
        Process special keyboard events (arrow keys, function keys, etc.)
        :param key: Special key code
        :param _: Other parameters
        :return:
        """
        if key == glut.GLUT_KEY_LEFT:  # left arrow
            current_scene_index[0] = (current_scene_index[0] - 1) % len(background_scenes)
            update_scene(drawings_list, background_scenes[current_scene_index[0]])
        elif key == glut.GLUT_KEY_RIGHT:  # right arrow
            current_scene_index[0] = (current_scene_index[0] + 1) % len(background_scenes)
            update_scene(drawings_list, background_scenes[current_scene_index[0]])

    return process_key, process_special_key


def create_animation_function(
    renderer: Renderer,
    drawings_list: list[Drawing],
    scanned_fish_queue: Queue,
    fish_queue: Queue,
    fish_limit: int,
    timer_msec: int,
    fish_shader_program: int = 0,
    bubble_texture: int = 0,
) -> Callable:
    """
    Wrapper for animation function
    :param renderer: Object of the Engine to draw all the objects
    :param drawings_list: Lists of sprites to draw
    :param scanned_fish_queue: Queue with scanning results
    :param fish_queue: Queue to maintain order of fish
    :param fish_limit: Maximum amount of fish to draw
    :param timer_msec: Timer interval value for animation
    :param fish_shader_program: ID of fish shader
    :param bubble_texture: ID of bubble texture
    :return: Function in the format for the GLUT
    """

    def animate(value):
        renderer.animate(drawings_list)
        glut.glutTimerFunc(timer_msec, animate, 0)

        # Get fish scan from scanner thread
        if scanned_fish_queue.qsize() > 0:
            scanned_fish = scanned_fish_queue.get()
            drawing = DrawingFish(
                Renderer.create_texture(scanned_fish), shader=fish_shader_program, bubble_texture_id=bubble_texture
            )
            drawings_list.append(drawing)
            fish_queue.put(drawing)

        if fish_queue.qsize() > fish_limit:
            fish = fish_queue.get()
            fish.go_away()

        # Remove dead fish from drawing list
        for drawing in drawings_list:
            if isinstance(drawing, DrawingFish) and not drawing.is_alive:
                drawings_list.remove(drawing)

    return animate


def main():
    # Initialize GLUT
    glut.glutInit()
    glut.glutInitDisplayMode(glut.GLUT_DOUBLE | glut.GLUT_RGB | glut.GLUT_DEPTH)  # pyright: ignore[reportOperatorIssue]

    # Request OpenGL 3.3 core profile
    glut.glutInitContextVersion(3, 3)
    glut.glutInitContextProfile(glut.GLUT_CORE_PROFILE)

    glut.glutInitWindowSize(800, 600)
    glut.glutCreateWindow(b"FishScanner")

    # Initialize OpenGL
    gl.glEnable(gl.GL_DEPTH_TEST)
    gl.glEnable(gl.GL_BLEND)
    gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)

    # Initialize OpenGL context
    gl.glClearColor(0.1, 0.1, 0.2, 1.0)
    gl.glViewport(0, 0, 800, 600)
    gl.glMatrixMode(gl.GL_PROJECTION)
    gl.glLoadIdentity()
    gl.glOrtho(-1, 1, -1, 1, -1, 1)
    gl.glMatrixMode(gl.GL_MODELVIEW)
    gl.glLoadIdentity()

    scanner = SimpleScanner()

    timer_msec = int(1000 / 60)  # 60 times per second
    renderer = Renderer()
    drawings_list = []
    cleanup_and_exit.drawings_list = drawings_list  # Store for cleanup

    fish_queue = Queue()  # Queue to maintain order of the fish
    fish_limit = 10  # Maximum amount of fish to draw
    scanned_fish_queue = Queue()

    # Initialize scenes configuration
    background_scenes = [
        {"type": "complex", "name": "Ocean"},
        {"type": "simple", "name": "Scene 2", "background": "ocean/images/scene2.jpg"},
        {"type": "simple", "name": "Scene 3", "background": "ocean/images/scene3.webp"},
    ]
    current_scene_index = [0]

    # Create display function first
    glut.glutDisplayFunc(partial(renderer.render, drawings_list))

    # Then initialize the scene
    update_scene(drawings_list, background_scenes[current_scene_index[0]])

    fish_shader_program = Renderer.create_shader(gl.GL_VERTEX_SHADER, FISH_SHADER_CODE)
    bubble_texture = Renderer.create_texture_from_file("ocean/images/bubble.png")
    load_fish_from_files(scanner, drawings_list, fish_queue, fish_shader_program, bubble_texture)

    # Store resources in cleanup function for proper deletion
    cleanup_and_exit.fish_shader = fish_shader_program
    cleanup_and_exit.bubble_texture = bubble_texture

    # Start the file watcher thread
    watcher_thread = Thread(target=watch_photos_directory, args=(scanner, scanned_fish_queue))
    watcher_thread.daemon = True  # Thread will exit when main program exits
    watcher_thread.start()

    glut.glutIgnoreKeyRepeat(True)
    key_handler, special_key_handler = create_key_processor(
        scanner, scanned_fish_queue, drawings_list, background_scenes, current_scene_index
    )
    glut.glutKeyboardFunc(key_handler)
    glut.glutSpecialFunc(special_key_handler)
    glut.glutTimerFunc(
        timer_msec,
        create_animation_function(
            renderer,
            drawings_list,
            scanned_fish_queue,
            fish_queue,
            fish_limit,
            timer_msec,
            fish_shader_program,
            bubble_texture,
        ),
        0,
    )

    # Start the main loop
    glut.glutMainLoop()


if __name__ == "__main__":
    main()
