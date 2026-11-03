from pathlib import Path

import cv2
import numpy as np
import OpenGL.GL as gl

from engine.drawing import Drawing
from engine.matrices import orthographic
from engine.shaders import compile_program


class Renderer:
    """
    Core of the Engine
    """

    def __init__(self, width: int, height: int, max_aspect: float | None = None):
        """
        Initialize OpenGL state for a framebuffer of the given size
        :param width: Framebuffer width in pixels
        :param height: Framebuffer height in pixels
        :param max_aspect: Widest world view to show; wider windows crop vertically instead of
            revealing space beyond the scene's backgrounds. None shows the full height always.
        """
        self._max_aspect = max_aspect
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)
        gl.glClearColor(0.1, 0.1, 0.2, 1.0)
        self.default_shader = compile_program()
        self.resize(width, height)

    def resize(self, width: int, height: int) -> None:
        """
        Fit the viewport and camera to a new framebuffer size, keeping world units square
        :param width: Framebuffer width in pixels
        :param height: Framebuffer height in pixels
        :return:
        """
        gl.glViewport(0, 0, width, height)
        aspect = width / height
        half_width = aspect if self._max_aspect is None else min(aspect, self._max_aspect)
        half_height = half_width / aspect
        # Y grows downwards on screen: smaller y is higher
        self.projection = orthographic(-half_width, half_width, half_height, -half_height, -1, 1)

    def render(self, drawings_list: list[Drawing]) -> None:
        """
        Draw all sprites
        :param drawings_list: List of sprites to draw
        :return:
        """
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)  # pyright: ignore[reportOperatorIssue]

        # Sort drawings by z-position, nearest (largest z) first
        sorted_drawings = sorted(self.all_sprites(drawings_list), key=lambda x: x.position[2], reverse=True)

        # First pass: render opaque objects
        gl.glDepthMask(gl.GL_TRUE)
        for drawing in sorted_drawings:
            if not drawing.is_transparent:
                drawing.render(self.projection, self.default_shader)

        # Second pass: render transparent objects farthest first, so nearer ones paint over them
        # (they do not write depth, so draw order is what decides which one shows)
        gl.glDepthMask(gl.GL_FALSE)  # Don't write to depth buffer for transparent objects
        for drawing in reversed(sorted_drawings):
            if drawing.is_transparent:
                drawing.render(self.projection, self.default_shader)

        gl.glDepthMask(gl.GL_TRUE)  # Reset depth mask

    def animate(
        self,
        drawings_list: list[Drawing],
    ) -> None:
        """
        Perform one step of animation
        :param drawings_list: List of sprites to animate
        :return:
        """
        for drawing in self.all_sprites(drawings_list):
            drawing.animation()

    @staticmethod
    def all_sprites(drawings_list: list[Drawing]) -> list[Drawing]:
        """
        Flatten sprites and their children (bubbles), parents first
        :param drawings_list: Top-level sprites
        :return: Every sprite to animate and draw
        """
        sprites: list[Drawing] = []
        pending = list(drawings_list)
        while pending:
            drawing = pending.pop(0)
            sprites.append(drawing)
            pending.extend(drawing.get_child_sprites())
        return sprites

    @staticmethod
    def create_texture(image: np.ndarray) -> int:
        """
        Create a texture from image represented by ndarray
        :param image: RGBA image to build texture
        :return: Texture ID
        """
        texid = gl.glGenTextures(1)
        gl.glBindTexture(gl.GL_TEXTURE_2D, texid)
        gl.glTexImage2D(
            gl.GL_TEXTURE_2D, 0, gl.GL_RGBA, image.shape[1], image.shape[0], 0, gl.GL_RGBA, gl.GL_UNSIGNED_BYTE, image
        )

        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_NEAREST)
        gl.glTexParameterf(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)

        gl.glBindTexture(gl.GL_TEXTURE_2D, 0)
        return texid

    @staticmethod
    def create_texture_from_file(filename: str | Path) -> int:
        """
        Create a texture from image loaded by the filename
        :param filename: Path to image with the texture
        :return: Texture ID
        """
        image = cv2.imread(str(filename), cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"Texture image not found or unreadable: {filename}")
        channels = 1 if image.ndim == 2 else image.shape[2]
        conversion = {1: cv2.COLOR_GRAY2RGBA, 3: cv2.COLOR_BGR2RGBA, 4: cv2.COLOR_BGRA2RGBA}[channels]
        return Renderer.create_texture(cv2.cvtColor(image, conversion))
