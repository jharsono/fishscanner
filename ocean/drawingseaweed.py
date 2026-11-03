from engine.drawing import Drawing
from engine.shaders import ShaderProgram

# Sine wave in sprite space driven by the timer, so the seaweed sways in place
SEAWEED_TRANSFORM = """
vec4 transform(vec3 p) {
    float pi = 3.14159;
    float A_x = 0.02;
    float A_y = 0.02;
    float w = 10.0 * pi;
    float t = 30.0 * pi / 180.0;
    float wave = sin(w * timer * p.y + t);
    return model * vec4(p.x + wave * A_x, p.y + wave * A_y, p.z, 1.0);
}
"""


class DrawingSeaweed(Drawing):
    """
    Sprite for seaweed
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
