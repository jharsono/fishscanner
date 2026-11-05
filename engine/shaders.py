"""GLSL shader sources and program compilation, for OpenGL 3.3 core and OpenGL ES 2.0.

Every sprite program shares the vertex inputs, uniforms and fragment shader below.
A sprite kind only supplies a `vec4 transform(vec3 p)` function that maps a mesh
vertex to world space; it may use the `model` matrix, the bouncing per-sprite `timer`
and `params`, four per-sprite numbers the sprite kind fills in (`Drawing.shader_params`).
The sources are written once; a `Dialect` supplies the first lines that differ between
GLSL 3.30 and GLSL ES 1.00, so the same transforms run on both.
"""

from dataclasses import dataclass

import OpenGL.GL as gl

# Vertex input locations, bound by name before linking so every program and mesh agree
POSITION_ATTRIBUTE = 0
TEXCOORD_ATTRIBUTE = 1


@dataclass(frozen=True)
class Dialect:
    """The opening lines of each shader for one GLSL version: its #version and the words that differ."""

    vertex: str
    fragment: str


CORE_DIALECT = Dialect(  # GLSL 3.30, for an OpenGL 3.3 core context
    vertex="#version 330 core\n#define IN in\n#define OUT out\n",
    fragment="#version 330 core\n#define IN in\n#define TEXTURE texture\nout vec4 frag_color;\n"
    "#define FRAG_COLOR frag_color\n",
)
GLES_DIALECT = Dialect(  # GLSL ES 1.00, for OpenGL ES 2.0 (the Raspberry Pi 3B)
    vertex="#version 100\n#define IN attribute\n#define OUT varying\n",
    fragment="#version 100\nprecision mediump float;\n#define IN varying\n#define TEXTURE texture2D\n"
    "#define FRAG_COLOR gl_FragColor\n",
)

VERTEX_HEADER = """
IN vec3 position;
IN vec2 texcoord;
uniform mat4 model;
uniform mat4 projection;
uniform float timer;
uniform vec4 params;
OUT vec2 v_texcoord;
"""

VERTEX_MAIN = """
void main() {
    gl_Position = projection * transform(position);
    v_texcoord = texcoord;
}
"""

DEFAULT_TRANSFORM = """
vec4 transform(vec3 p) {
    return model * vec4(p, 1.0);
}
"""

FRAGMENT_SHADER = """
IN vec2 v_texcoord;
uniform sampler2D tex;
uniform vec3 color;
void main() {
    vec4 texel = TEXTURE(tex, v_texcoord);
    if (texel.a <= 0.1) {
        discard;
    }
    FRAG_COLOR = vec4(texel.rgb * color, texel.a);
}
"""


@dataclass(frozen=True)
class ShaderProgram:
    """A linked program and the locations of the uniforms every sprite sets."""

    id: int
    model: int
    projection: int
    timer: int
    params: int
    color: int


def is_gles() -> bool:
    """Whether the current context is OpenGL ES rather than desktop OpenGL."""
    version: bytes = gl.glGetString(gl.GL_VERSION)  # pyright: ignore[reportAssignmentType]
    return version.startswith(b"OpenGL ES")  # The prefix the GLES specification requires


def _compile(shader_type: int, source: str) -> int:
    shader: int = gl.glCreateShader(shader_type)  # pyright: ignore[reportAssignmentType]
    gl.glShaderSource(shader, source.strip())
    gl.glCompileShader(shader)
    if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
        raise RuntimeError(gl.glGetShaderInfoLog(shader).decode())
    return shader


def compile_program(transform_source: str = DEFAULT_TRANSFORM) -> ShaderProgram:
    """
    Build a sprite program around a vertex transform function
    :param transform_source: GLSL defining `vec4 transform(vec3 p)`
    :return: Linked program with its uniform locations
    """
    dialect = GLES_DIALECT if is_gles() else CORE_DIALECT
    vertex = _compile(gl.GL_VERTEX_SHADER, dialect.vertex + VERTEX_HEADER + transform_source + VERTEX_MAIN)
    fragment = _compile(gl.GL_FRAGMENT_SHADER, dialect.fragment + FRAGMENT_SHADER)
    program: int = gl.glCreateProgram()  # pyright: ignore[reportAssignmentType]
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
    gl.glBindAttribLocation(program, POSITION_ATTRIBUTE, "position")
    gl.glBindAttribLocation(program, TEXCOORD_ATTRIBUTE, "texcoord")
    gl.glLinkProgram(program)
    gl.glDeleteShader(vertex)
    gl.glDeleteShader(fragment)
    if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
        raise RuntimeError(gl.glGetProgramInfoLog(program).decode())
    gl.glUseProgram(program)
    gl.glUniform1i(gl.glGetUniformLocation(program, "tex"), 0)
    gl.glUseProgram(0)
    return ShaderProgram(
        id=program,
        model=gl.glGetUniformLocation(program, "model"),
        projection=gl.glGetUniformLocation(program, "projection"),
        timer=gl.glGetUniformLocation(program, "timer"),
        params=gl.glGetUniformLocation(program, "params"),
        color=gl.glGetUniformLocation(program, "color"),
    )
