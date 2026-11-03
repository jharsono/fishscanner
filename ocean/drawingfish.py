import numpy as np

from engine.drawing import Drawing
from engine.shaders import ShaderProgram
from ocean.drawingbubble import DrawingBubble

# Sine wave along the body in world space, so it travels along the fish as it swims
FISH_TRANSFORM = """
vec4 transform(vec3 p) {
    vec4 world = model * vec4(p, 1.0);
    float pi = 3.14159;
    float A_x = 0.001;
    float A_y = 0.01;
    float w = 10.0 * pi;
    float t = 30.0 * pi / 180.0;
    float wave = sin(w * world.x + t);
    return vec4(world.x + wave * A_x, world.y + wave * A_y, world.z, world.w);
}
"""


class DrawingFish(Drawing):
    """
    Sprite for drawing of fish
    """

    def __init__(
        self,
        texid: int,
        grid_x: int = 5,
        grid_y: int = 5,
        shader: ShaderProgram | None = None,
        bubble_texture_id: int = 0,
    ):
        """
        Set default position of fish and select default vector of moving
        :param texid: ID of texture
        :param grid_x: Mesh elements along axis X
        :param grid_y: Mesh elements along axis Y
        :param shader: Sprite program, or None for the renderer's default
        :param bubble_texture_id: ID of a bubble texture
        """
        super().__init__(texid, grid_x, grid_y, shader)
        self.is_transparent = True  # Mark fish as transparent for proper rendering
        self.scale = np.array([1.0, 0.75, 0.3])
        self.vector = np.array([0, 0.02, 0.0])
        self.is_alive = True  # The fish will be deleted from the drawing list when it False

        self._left = -1.5
        self._right = 1.5
        self._top = -0.7
        self._bottom = 0.3

        # Randomly choose entry direction (0: left, 1: right, 2: top, 3: bottom)
        entry_direction = np.random.randint(4)
        if entry_direction == 0:  # From left
            self.position = np.array([-2.0, np.random.uniform(self._top, self._bottom), 0.0])
            self.vector = np.array([0.02, 0.0, 0.0])
        elif entry_direction == 1:  # From right
            self.position = np.array([2.0, np.random.uniform(self._top, self._bottom), 0.0])
            self.vector = np.array([-0.02, 0.0, 0.0])
            self.scale[0] = -abs(self.scale[0])  # Face left
        elif entry_direction == 2:  # From top
            self.position = np.array([np.random.uniform(self._left, self._right), -1, 0.0])
            self.vector = np.array([0.0, 0.02, 0.0])
        else:  # From bottom
            self.position = np.array([np.random.uniform(self._left, self._right), 0.5, 0.0])
            self.vector = np.array([0.0, -0.02, 0.0])

        # Randomly flip horizontal direction for variety
        if np.random.randint(2) == 0 and (entry_direction in [2, 3]):  # Only for vertical entry
            self.scale[0] = -self.scale[0]
            self.vector[0] = np.random.uniform(-0.01, 0.01)  # Add slight horizontal movement

        # Parameters for animations
        self._animation_stage = "init"
        self._init_animation_step = np.random.randint(60, 180)  # Random start time between 1-3 seconds at 60fps
        self._water_resistance = np.random.uniform(0.95, 0.98)

        # To animate bubbles
        self._bubble_texture_id = bubble_texture_id
        self._bubble_random_frequency = 2
        self._bubble_deviation_x = 0
        self._bubble_speed_y = -0.01
        self._bubbles = []

    def _init_fish_velocity(self) -> None:
        """
        Setup initial values for velocity vector
        :return:
        """
        self.vector = np.array([np.random.uniform(0.002, 0.003), np.random.uniform(0.001, 0.002), 0.0])
        if self.scale[0] < 0:
            self.vector[0] = -self.vector[0]
        if np.random.randint(2) == 0:
            self.vector[1] = -self.vector[1]

        self._bubble_random_frequency = 500
        self._bubble_deviation_x = 0.1
        self._bubble_speed_y = -0.005

    def _process_bubbles(self) -> None:
        # randomly create bubble
        if np.random.randint(int(self._bubble_random_frequency)) == 0:
            bubble_x = np.random.uniform(self.position[0], self.position[0] + self.scale[0] / 2)
            bubble = DrawingBubble(self._bubble_texture_id, start_x=bubble_x, start_y=self.position[1])
            bubble.deviation_x = self._bubble_deviation_x
            bubble.speed_y = self._bubble_speed_y
            self._bubbles.append(bubble)

        # delete bubbles when they left the screen
        self._bubbles = [bubble for bubble in self._bubbles if bubble.position[1] >= -1]

    def animation(self) -> None:
        """
        Logic of movement of the fish
        :return:
        """
        self.position += self.vector
        self._process_bubbles()

        if self._animation_stage == "init":
            self._init_animation_step -= 1
            self._bubble_random_frequency += 0.1
            self.vector[1] *= self._water_resistance
            # Finis init animation
            if self._init_animation_step == 0:
                self._init_fish_velocity()
                self._animation_stage = "swim"

        elif self._animation_stage == "swim":
            # If we near border go to the other direction
            if self.position[0] > self._right or self.position[0] < self._left:
                self.vector[0] = -self.vector[0]
                self.rotation_vector[1] = 5.0

            if self.position[1] < self._top or self.position[1] > self._bottom:
                self.vector[1] = -self.vector[1]

            self.rotate[1] = (self.rotate[1] + self.rotation_vector[1]) % 360

            if self.rotate[1] % 180 == 0:
                self.rotation_vector[1] = 0.0

        elif self._animation_stage == "finish":
            if self.position[0] > self._right + 1.0 or self.position[0] < self._left - 1.0:
                self.is_alive = False

    def get_child_sprites(self) -> list[Drawing]:
        """
        Return list of bubbles
        :return: List of bubbles
        """
        return self._bubbles

    def go_away(self) -> None:
        """
        Start animation of fish swimming away
        :return:
        """
        self.vector[1] = 0.0
        self.vector[0] *= 2
        self._animation_stage = "finish"
