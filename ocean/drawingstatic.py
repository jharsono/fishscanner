from engine.drawing import Drawing
from engine.shaders import ShaderProgram


class DrawingStatic(Drawing):
    """
    Sprite for static objects
    """

    def __init__(
        self,
        texid: int,
        grid_x: int = 5,
        grid_y: int = 5,
        shader: ShaderProgram | None = None,
    ):
        """
        Initialize seaweed as default sprite. All the magic happens in the shader
        :param texid: ID of texture
        :param grid_x: Mesh elements along axis X
        :param grid_y: Mesh elements along axis Y
        :param shader: Sprite program, or None for the renderer's default
        """
        super().__init__(texid, grid_x, grid_y, shader)
