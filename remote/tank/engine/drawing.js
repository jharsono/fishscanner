// Draw and animate a 3D sprite: a unit quad subdivided into a grid of triangles, so vertex shaders can bend it.
import { columnMajor, modelMatrix } from "./matrices.js";
import { POSITION_ATTRIBUTE, TEXCOORD_ATTRIBUTE } from "./shaders.js";

const FLOAT_BYTES = 4;
const VERTEX_STRIDE = 5 * FLOAT_BYTES; // Interleaved position (x, y, z) and texture coordinate (s, t)

// Meshes are uploaded once per grid size and shared by every sprite of that size, per WebGL context
const meshesByContext = new WeakMap();

function meshFor(gl, gridX, gridY) {
  let meshes = meshesByContext.get(gl);
  if (meshes === undefined) {
    meshes = new Map();
    meshesByContext.set(gl, meshes);
  }
  const key = `${gridX}x${gridY}`;
  if (!meshes.has(key)) {
    meshes.set(key, createMesh(gl, gridX, gridY));
  }
  return meshes.get(key);
}

/**
 * Upload a unit quad subdivided into triangles
 * @param {WebGLRenderingContext} gl Context to upload it to
 * @param {number} gridSizeX Mesh elements along axis X
 * @param {number} gridSizeY Mesh elements along axis Y
 * @returns {{buffer: WebGLBuffer, vertexCount: number}} Mesh handles
 */
function createMesh(gl, gridSizeX, gridSizeY) {
  const vertices = [];
  const stepX = 1 / gridSizeX;
  const stepY = 1 / gridSizeY;
  for (let row = 0; row < gridSizeY; row++) {
    const y = -0.5 + row * stepY;
    for (let col = 0; col < gridSizeX; col++) {
      const x = -0.5 + col * stepX;
      for (const [px, py] of [
        [x, y],
        [x + stepX, y],
        [x, y + stepY],
        [x + stepX, y],
        [x, y + stepY],
        [x + stepX, y + stepY],
      ]) {
        vertices.push(px, py, 0.0, px + 0.5, py + 0.5);
      }
    }
  }
  const buffer = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(vertices), gl.STATIC_DRAW);
  return { buffer, vertexCount: vertices.length / 5 };
}

export class Drawing {
  /**
   * Setup default position for sprite
   * @param {WebGLTexture|null} texture Texture to draw the sprite with
   * @param {{gridX?: number, gridY?: number, shader?: object|null}} options Mesh elements along X and Y,
   *   and the sprite program, or null for the renderer's default
   */
  constructor(texture, { gridX = 5, gridY = 5, shader = null } = {}) {
    // Setup default positions of sprite
    this.position = [0, 0.0, 0.0];
    this.rotate = [0.0, 0.0, 0.0];
    this.scale = [1.0, 1.0, 1.0];
    this.color = [1.0, 1.0, 1.0];
    this.shaderParams = [0, 0, 0, 0]; // Passed to the program as `params`
    // Transparent sprites are rendered in a second pass without depth writes
    this.isTransparent = false;

    // Setup default animation settings
    this.maxAnimationTimer = 1;
    this.stepAnimationTimer = 0.001;

    // Setup default vectors for image transformation
    this.vector = [0.0, 0.0, 0.0];
    this.rotationVector = [0.0, 0.0, 0.0];

    this.texture = texture;
    this._shader = shader;
    this._timeCounter = 0.0;
    this._grid = [gridX, gridY];
  }

  /**
   * Render sprite with attached texture and shader
   * @param {WebGLRenderingContext} gl Context to draw in
   * @param {number[]} projection Camera projection matrix
   * @param {object} defaultShader Program used when the sprite has none of its own
   */
  render(gl, projection, defaultShader) {
    const shader = this._shader || defaultShader;
    gl.useProgram(shader.program);
    gl.uniformMatrix4fv(shader.model, false, columnMajor(modelMatrix(this.position, this.rotate, this.scale)));
    gl.uniformMatrix4fv(shader.projection, false, columnMajor(projection));
    gl.uniform3f(shader.color, this.color[0], this.color[1], this.color[2]);
    gl.uniform1f(shader.timer, this._timeCounter);
    gl.uniform4f(shader.params, this.shaderParams[0], this.shaderParams[1], this.shaderParams[2], this.shaderParams[3]);
    this._timeCounter += this.stepAnimationTimer;
    // If timer came to border - go back
    if (this._timeCounter >= this.maxAnimationTimer || this._timeCounter <= 0) {
      this.stepAnimationTimer = -this.stepAnimationTimer;
    }
    const mesh = meshFor(gl, this._grid[0], this._grid[1]); // Created on first render, so sprites need no context to exist
    gl.bindTexture(gl.TEXTURE_2D, this.texture);
    // WebGL 1 has no vertex array objects, so every draw points the vertex inputs at its own mesh
    gl.bindBuffer(gl.ARRAY_BUFFER, mesh.buffer);
    gl.vertexAttribPointer(POSITION_ATTRIBUTE, 3, gl.FLOAT, false, VERTEX_STRIDE, 0);
    gl.vertexAttribPointer(TEXCOORD_ATTRIBUTE, 2, gl.FLOAT, false, VERTEX_STRIDE, 3 * FLOAT_BYTES);
    gl.drawArrays(gl.TRIANGLES, 0, mesh.vertexCount);
  }

  /** Override this method to apply animation */
  animation() {}

  /** Override this method to return all Drawings that are children of the current one */
  getChildSprites() {
    return [];
  }
}
