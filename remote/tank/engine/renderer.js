// Core of the engine.
import { orthographic } from "./matrices.js";
import { compileProgram, POSITION_ATTRIBUTE, TEXCOORD_ATTRIBUTE } from "./shaders.js";

// Opaque, so blending cannot leave the canvas translucent where transparent sprites draw over the
// background (the page would show through); no antialiasing, like the desktop window, which also
// spares a TV's GPU
export const CONTEXT_ATTRIBUTES = { alpha: false, antialias: false };

export class Renderer {
  /**
   * Initialize WebGL state for a drawing buffer of the given size
   * @param {WebGLRenderingContext} gl Context to draw in
   * @param {number} width Drawing buffer width in pixels
   * @param {number} height Drawing buffer height in pixels
   * @param {number|null} maxAspect Widest world view to show; wider windows crop vertically instead of
   *   revealing space beyond the scene's backgrounds. null shows the full height always.
   */
  constructor(gl, width, height, maxAspect = null) {
    this.gl = gl;
    this._maxAspect = maxAspect;
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.DEPTH_TEST);
    gl.depthFunc(gl.LEQUAL);
    gl.clearColor(0.1, 0.1, 0.2, 1.0);
    // Every program reads both inputs, from whichever mesh a draw points them at
    gl.enableVertexAttribArray(POSITION_ATTRIBUTE);
    gl.enableVertexAttribArray(TEXCOORD_ATTRIBUTE);
    this.defaultShader = compileProgram(gl);
    this.resize(width, height);
  }

  /**
   * Fit the viewport and camera to a new drawing buffer size, keeping world units square
   * @param {number} width Drawing buffer width in pixels
   * @param {number} height Drawing buffer height in pixels
   */
  resize(width, height) {
    this.gl.viewport(0, 0, width, height);
    const aspect = width / height;
    const halfWidth = this._maxAspect === null ? aspect : Math.min(aspect, this._maxAspect);
    const halfHeight = halfWidth / aspect;
    // Y grows downwards on screen: smaller y is higher
    this.projection = orthographic(-halfWidth, halfWidth, halfHeight, -halfHeight, -1, 1);
  }

  /**
   * Draw all sprites
   * @param {Array} drawingsList List of sprites to draw
   */
  render(drawingsList) {
    const gl = this.gl;
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);

    // Sort drawings by z-position, nearest (largest z) first; the sort is stable, so equal depths keep their order
    const sortedDrawings = Renderer.allSprites(drawingsList).sort((a, b) => b.position[2] - a.position[2]);

    // First pass: render opaque objects
    gl.depthMask(true);
    for (const drawing of sortedDrawings) {
      if (!drawing.isTransparent) {
        drawing.render(gl, this.projection, this.defaultShader);
      }
    }

    // Second pass: render transparent objects farthest first, so nearer ones paint over them
    // (they do not write depth, so draw order is what decides which one shows)
    gl.depthMask(false); // Don't write to depth buffer for transparent objects
    for (let i = sortedDrawings.length - 1; i >= 0; i--) {
      if (sortedDrawings[i].isTransparent) {
        sortedDrawings[i].render(gl, this.projection, this.defaultShader);
      }
    }

    gl.depthMask(true); // Reset depth mask
  }

  /**
   * Perform one step of animation
   * @param {Array} drawingsList List of sprites to animate
   */
  animate(drawingsList) {
    for (const drawing of Renderer.allSprites(drawingsList)) {
      drawing.animation();
    }
  }

  /**
   * Flatten sprites and their children (bubbles), parents first
   * @param {Array} drawingsList Top-level sprites
   * @returns {Array} Every sprite to animate and draw
   */
  static allSprites(drawingsList) {
    const sprites = [];
    const pending = [...drawingsList];
    while (pending.length > 0) {
      const drawing = pending.shift();
      sprites.push(drawing);
      pending.push(...drawing.getChildSprites());
    }
    return sprites;
  }
}

/**
 * Create a texture from an image; its first row is the top of the sprite
 * @param {WebGLRenderingContext} gl Context to create it in
 * @param {TexImageSource} image Image, ImageData or canvas
 * @returns {WebGLTexture} The texture
 */
export function createTexture(gl, image) {
  const texture = gl.createTexture();
  fillTexture(gl, texture, image);
  return texture;
}

/** Replace a texture's image, keeping the texture */
export function fillTexture(gl, texture, image) {
  gl.bindTexture(gl.TEXTURE_2D, texture);
  // The image's own values, as the desktop app (OpenCV) reads them: the backgrounds carry an Adobe
  // RGB profile, and converting them to sRGB would shift the water's colour
  gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
  // Clamped and without mipmaps, which is what WebGL 1 allows for sizes that are not powers of two
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
  gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
  gl.bindTexture(gl.TEXTURE_2D, null);
}

/**
 * Load and decode an image
 * @param {string} url Where the image is served
 * @returns {Promise<HTMLImageElement>} The decoded image; rejects if it cannot be fetched or decoded
 */
export async function loadImage(url) {
  const image = new Image();
  image.src = url;
  await image.decode();
  return image;
}
