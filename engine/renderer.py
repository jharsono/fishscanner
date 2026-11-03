from queue import Queue

import cv2
import numpy as np
import OpenGL.GL as gl
import OpenGL.GLUT as glut

from engine.drawing import Drawing


class Renderer:
    """
    Core of the Engine
    """

    def __init__(self):
        """
        Initialize OpenGL state
        """
        gl.glEnable(gl.GL_TEXTURE_2D)
        gl.glDisable(gl.GL_LIGHTING)
        gl.glEnable(gl.GL_BLEND)
        gl.glBlendFunc(gl.GL_SRC_ALPHA, gl.GL_ONE_MINUS_SRC_ALPHA)
        gl.glEnableClientState(gl.GL_VERTEX_ARRAY)

        # Enable depth testing
        gl.glEnable(gl.GL_DEPTH_TEST)
        gl.glDepthFunc(gl.GL_LEQUAL)

        # Enable alpha testing to handle transparency better
        gl.glEnable(gl.GL_ALPHA_TEST)
        gl.glAlphaFunc(gl.GL_GREATER, 0.1)  # Only render pixels with alpha > 0.1

        # Get current window dimensions
        width = glut.glutGet(glut.GLUT_WINDOW_WIDTH)
        height = glut.glutGet(glut.GLUT_WINDOW_HEIGHT)
        gl.glViewport(0, 0, width, height)
        gl.glMatrixMode(gl.GL_PROJECTION)
        gl.glLoadIdentity()
        aspect = width / height
        gl.glOrtho(-aspect, aspect, 1, -1, -1, 1)

        gl.glMatrixMode(gl.GL_MODELVIEW)
        gl.glLoadIdentity()

    @staticmethod
    def render(drawings_list: list[Drawing]) -> None:
        """
        Draw all sprites
        :param drawings_list: List of sprites to draw
        :return:
        """
        gl.glClear(gl.GL_COLOR_BUFFER_BIT | gl.GL_DEPTH_BUFFER_BIT)  # pyright: ignore[reportOperatorIssue]

        # Sort drawings by z-position (back to front)
        sorted_drawings = sorted(drawings_list, key=lambda x: x.position[2], reverse=True)

        # First pass: render opaque objects
        gl.glDepthMask(gl.GL_TRUE)
        for drawing in sorted_drawings:
            if not drawing.is_transparent:
                drawing.render()

        # Second pass: render transparent objects
        gl.glDepthMask(gl.GL_FALSE)  # Don't write to depth buffer for transparent objects
        for drawing in sorted_drawings:
            if drawing.is_transparent:
                drawing.render()

        gl.glDepthMask(gl.GL_TRUE)  # Reset depth mask
        gl.glFlush()
        glut.glutSwapBuffers()

    def animate(
        self,
        drawings_list: list[Drawing],
    ) -> None:
        """
        Perform one step of animation
        :param drawings_list: List of sprites to animate
        :return:
        """
        drawings_queue = Queue()
        for drawing in drawings_list:
            drawing.animation()
            for child in drawing.get_child_sprites():
                drawings_queue.put(child)

        while drawings_queue.qsize() > 0:
            drawing = drawings_queue.get()
            drawing.animation()
            for child in drawing.get_child_sprites():
                drawings_queue.put(child)

        glut.glutPostRedisplay()

    @staticmethod
    def create_texture(image: np.ndarray) -> int:
        """
        Create a texture from image represented by ndarray
        :param image: Image to build texture
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
    def create_texture_from_file(filename: str) -> int:
        """
        Create a texture from image loaded by the filename
        :param filename: Path to image with the texture
        :return: Texture ID
        """
        image = cv2.imread(filename, cv2.IMREAD_UNCHANGED)
        if image is None:
            raise FileNotFoundError(f"Texture image not found or unreadable: {filename}")
        image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGRA)
        return Renderer.create_texture(image)

    @staticmethod
    def create_shader(
        shader_type: gl.Constant,
        source: str,
    ) -> int:
        """
        Compile shader from string
        :param shader_type:  Type of shader
        :param source: Code of the shader represented by the string
        :return: Shader ID
        """
        shader = gl.glCreateShader(shader_type)
        gl.glShaderSource(shader, source)
        gl.glCompileShader(shader)
        result = gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS)
        if not result:
            raise RuntimeError(gl.glGetShaderInfoLog(shader))

        shader_program = gl.glCreateProgram()
        gl.glAttachShader(shader_program, shader)
        gl.glLinkProgram(shader_program)
        return shader_program  # pyright: ignore[reportReturnType]
