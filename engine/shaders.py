"""GLSL 3.30 shader sources and program compilation.

Every sprite program shares the vertex inputs, uniforms and fragment shader below.
A sprite kind only supplies a `vec4 transform(vec3 p)` function that maps a mesh
vertex to world space; it may use the `model` matrix, the bouncing per-sprite `timer`
and the continuous `time` in seconds since the app started.
"""

from dataclasses import dataclass

import OpenGL.GL as gl

VERTEX_HEADER = """
#version 330 core
layout(location = 0) in vec3 position;
layout(location = 1) in vec2 texcoord;
uniform mat4 model;
uniform mat4 projection;
uniform float timer;
uniform float time;
out vec2 v_texcoord;
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
#version 330 core
in vec2 v_texcoord;
uniform sampler2D tex;
uniform vec3 color;
out vec4 frag_color;
void main() {
    vec4 texel = texture(tex, v_texcoord);
    if (texel.a <= 0.1) {
        discard;
    }
    frag_color = vec4(texel.rgb * color, texel.a);
}
"""


@dataclass(frozen=True)
class ShaderProgram:
    """A linked program and the locations of the uniforms every sprite sets."""

    id: int
    model: int
    projection: int
    timer: int
    time: int
    color: int


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
    vertex = _compile(gl.GL_VERTEX_SHADER, VERTEX_HEADER + transform_source + VERTEX_MAIN)
    fragment = _compile(gl.GL_FRAGMENT_SHADER, FRAGMENT_SHADER)
    program: int = gl.glCreateProgram()  # pyright: ignore[reportAssignmentType]
    gl.glAttachShader(program, vertex)
    gl.glAttachShader(program, fragment)
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
        time=gl.glGetUniformLocation(program, "time"),
        color=gl.glGetUniformLocation(program, "color"),
    )
