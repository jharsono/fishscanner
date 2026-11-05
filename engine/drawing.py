from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import OpenGL.GL as gl

from engine.matrices import column_major, model_matrix
from engine.shaders import POSITION_ATTRIBUTE, TEXCOORD_ATTRIBUTE, ShaderProgram, is_gles

FLOAT_BYTES = 4
VERTEX_STRIDE = 5 * FLOAT_BYTES  # Interleaved position (x, y, z) and texture coordinate (s, t)


@dataclass(frozen=True)
class Mesh:
    """A unit quad subdivided into triangles, uploaded once and shared by every sprite of that grid size."""

    vbo: int
    vertex_count: int


class Drawing:
    """
    Draw and animate 3D sprite
    """

    _meshes: dict[tuple[int, int], Mesh] = {}
    # A core profile draws nothing without a vertex array object bound and OpenGL ES 2.0 has none,
    # so one stays bound on core profiles and every draw points the vertex inputs at its own mesh
    _vertex_array: int | None = None

    def __init__(
        self,
        texid: int,
        grid_x: int = 5,
        grid_y: int = 5,
        shader: ShaderProgram | None = None,
    ):
        """
        Setup default position for sprite. Select mesh of selected size.
        :param texid: ID of texture
        :param grid_x: Mesh elements along axis X
        :param grid_y: Mesh elements along axis Y
        :param shader: Sprite program, or None for the renderer's default
        """

        # Setup default positions of sprite
        self.position = np.array([0, 0.0, 0.0])
        self.rotate = np.array([0.0, 0.0, 0.0])
        self.scale = np.array([1.0, 1.0, 1.0])
        self.color = np.array([1.0, 1.0, 1.0])
        self.shader_params = np.zeros(4, dtype=np.float32)  # Passed to the program as `params`
        # Transparent sprites are rendered in a second pass without depth writes
        self.is_transparent = False

        # Setup default animation settings
        self.max_animation_timer = 1
        self.step_animation_timer = 0.001

        # Setup default vectors for image transformation
        self.vector = np.array([0.0, 0.0, 0.0])
        self.rotation_vector = np.array([0.0, 0.0, 0.0])

        self._texid = texid
        self._shader = shader
        self._time_counter = 0.0
        self._grid = (grid_x, grid_y)

    @property
    def texid(self) -> int:
        return self._texid

    def render(self, projection: np.ndarray, default_shader: ShaderProgram) -> None:
        """
        Render sprite with attached texture and shader
        :param projection: Camera projection matrix
        :param default_shader: Program used when the sprite has none of its own
        :return:
        """
        shader = self._shader or default_shader
        gl.glUseProgram(shader.id)
        model = model_matrix(self.position, self.rotate, self.scale)
        gl.glUniformMatrix4fv(shader.model, 1, gl.GL_FALSE, column_major(model))
        gl.glUniformMatrix4fv(shader.projection, 1, gl.GL_FALSE, column_major(projection))
        gl.glUniform3f(shader.color, *self.color)
        gl.glUniform1f(shader.timer, self._time_counter)
        gl.glUniform4f(shader.params, *self.shader_params)
        self._time_counter += self.step_animation_timer
        # If timer came to border - go back
        if self._time_counter >= self.max_animation_timer or self._time_counter <= 0:
            self.step_animation_timer = -self.step_animation_timer
        mesh = self._mesh_for(*self._grid)  # Created on first render, so sprites need no GL context to exist
        gl.glBindTexture(gl.GL_TEXTURE_2D, self._texid)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, mesh.vbo)
        gl.glVertexAttribPointer(POSITION_ATTRIBUTE, 3, gl.GL_FLOAT, gl.GL_FALSE, VERTEX_STRIDE, gl.ctypes.c_void_p(0))
        texcoord_offset = gl.ctypes.c_void_p(3 * FLOAT_BYTES)
        gl.glVertexAttribPointer(TEXCOORD_ATTRIBUTE, 2, gl.GL_FLOAT, gl.GL_FALSE, VERTEX_STRIDE, texcoord_offset)
        gl.glDrawArrays(gl.GL_TRIANGLES, 0, mesh.vertex_count)
        gl.glUseProgram(0)

    def animation(self) -> None:
        """
        Override this method to apply animation
        :return:
        """
        pass

    def get_child_sprites(self) -> list[Drawing]:
        """
        Override this method to return all Drawings that child for the current one
        :return: List of child drawings
        """
        return []

    @classmethod
    def _mesh_for(cls, grid_x: int, grid_y: int) -> Mesh:
        if not cls._meshes:
            cls._enable_vertex_inputs()
        key = (grid_x, grid_y)
        if key not in cls._meshes:
            cls._meshes[key] = cls._mesh_create(grid_x, grid_y)
        return cls._meshes[key]

    @classmethod
    def _enable_vertex_inputs(cls) -> None:
        """Turn on the position and texture coordinate inputs, in the vertex array on core profiles."""
        if not is_gles():
            cls._vertex_array = gl.glGenVertexArrays(1)
            gl.glBindVertexArray(cls._vertex_array)
        gl.glEnableVertexAttribArray(POSITION_ATTRIBUTE)
        gl.glEnableVertexAttribArray(TEXCOORD_ATTRIBUTE)

    @classmethod
    def release_meshes(cls) -> None:
        """Delete every shared mesh from the GPU; call once before the context goes away."""
        for mesh in cls._meshes.values():
            gl.glDeleteBuffers(1, [mesh.vbo])
        cls._meshes.clear()
        if cls._vertex_array is not None:
            gl.glDeleteVertexArrays(1, [cls._vertex_array])
            cls._vertex_array = None

    @staticmethod
    def _mesh_create(grid_size_x: int, grid_size_y: int) -> Mesh:
        """
        Upload a mesh of selected size: interleaved position (x, y, z) and texture coordinate (s, t)
        :param grid_size_x: Mesh elements along axis X
        :param grid_size_y: Mesh elements along axis Y
        :return: Mesh handles
        """
        vertices = []
        step_x = 1 / grid_size_x
        step_y = 1 / grid_size_y

        for y in np.arange(-0.5, 0.5, step_y):
            for x in np.arange(-0.5, 0.5, step_x):
                for px, py in [
                    (x, y),
                    (x + step_x, y),
                    (x, y + step_y),
                    (x + step_x, y),
                    (x, y + step_y),
                    (x + step_x, y + step_y),
                ]:
                    vertices += [px, py, 0.0, px + 0.5, py + 0.5]
        data = np.array(vertices, dtype=np.float32)

        vbo = gl.glGenBuffers(1)
        gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vbo)
        gl.glBufferData(gl.GL_ARRAY_BUFFER, data.nbytes, data, gl.GL_STATIC_DRAW)
        return Mesh(vbo=vbo, vertex_count=len(data) // 5)
