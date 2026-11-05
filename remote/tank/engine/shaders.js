// GLSL ES 1.00 (the shading language of WebGL 1) sources and program compilation.
//
// Every sprite program shares the vertex inputs, uniforms and fragment shader below. A sprite kind
// only supplies a `vec4 transform(vec3 p)` function that maps a mesh vertex to world space; it may
// use the `model` matrix, the bouncing per-sprite `timer` and `params`, four per-sprite numbers the
// sprite kind fills in (`Drawing.shaderParams`).

// Vertex input locations, bound by name before linking so every program and mesh agree
export const POSITION_ATTRIBUTE = 0;
export const TEXCOORD_ATTRIBUTE = 1;

const VERTEX_HEADER = `#version 100
attribute vec3 position;
attribute vec2 texcoord;
uniform mat4 model;
uniform mat4 projection;
uniform float timer;
uniform vec4 params;
varying vec2 v_texcoord;
`;

const VERTEX_MAIN = `
void main() {
    gl_Position = projection * transform(position);
    v_texcoord = texcoord;
}
`;

const DEFAULT_TRANSFORM = `
vec4 transform(vec3 p) {
    return model * vec4(p, 1.0);
}
`;

// Texels with alpha at or below 0.1 are discarded, so transparent sprites leave no edges in the depth buffer
const FRAGMENT_SHADER = `#version 100
precision mediump float;
varying vec2 v_texcoord;
uniform sampler2D tex;
uniform vec3 color;
void main() {
    vec4 texel = texture2D(tex, v_texcoord);
    if (texel.a <= 0.1) {
        discard;
    }
    gl_FragColor = vec4(texel.rgb * color, texel.a);
}
`;

function compile(gl, type, source) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(gl.getShaderInfoLog(shader));
  }
  return shader;
}

/**
 * Build a sprite program around a vertex transform function
 * @param {WebGLRenderingContext} gl Context to build it in
 * @param {string} transformSource GLSL defining `vec4 transform(vec3 p)`
 * @returns {{program: WebGLProgram, model, projection, timer, params, color}} Linked program with
 *   its uniform locations (null for a uniform the transform does not use)
 */
export function compileProgram(gl, transformSource = DEFAULT_TRANSFORM) {
  const vertex = compile(gl, gl.VERTEX_SHADER, VERTEX_HEADER + transformSource + VERTEX_MAIN);
  const fragment = compile(gl, gl.FRAGMENT_SHADER, FRAGMENT_SHADER);
  const program = gl.createProgram();
  gl.attachShader(program, vertex);
  gl.attachShader(program, fragment);
  gl.bindAttribLocation(program, POSITION_ATTRIBUTE, "position");
  gl.bindAttribLocation(program, TEXCOORD_ATTRIBUTE, "texcoord");
  gl.linkProgram(program);
  gl.deleteShader(vertex);
  gl.deleteShader(fragment);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(gl.getProgramInfoLog(program));
  }
  gl.useProgram(program);
  gl.uniform1i(gl.getUniformLocation(program, "tex"), 0);
  return {
    program,
    model: gl.getUniformLocation(program, "model"),
    projection: gl.getUniformLocation(program, "projection"),
    timer: gl.getUniformLocation(program, "timer"),
    params: gl.getUniformLocation(program, "params"),
    color: gl.getUniformLocation(program, "color"),
  };
}
