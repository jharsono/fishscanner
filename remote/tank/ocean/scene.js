// Everything that is drawn, plus the textures and programs needed to build and rebuild it.
import { createTexture, fillTexture, loadImage } from "../engine/renderer.js";
import { compileProgram } from "../engine/shaders.js";
import { DrawingFish, FISH_TRANSFORM, mod } from "./drawingfish.js";
import { DrawingSeaweed, SEAWEED_TRANSFORM } from "./drawingseaweed.js";
import { DrawingStatic } from "./drawingstatic.js";

const IMAGES_URL = "/images/"; // Where the server serves ocean/images
export const BACKGROUND_SCALE = [3.6, 2.0, 1.0]; // Background sprites cover this much of the world, centred on the origin
// What a decoration shows until its image has loaded: one transparent pixel, which the fragment shader discards
const NOT_LOADED = new ImageData(1, 1);

export class Scene {
  /** @param {WebGLRenderingContext} gl Context to build the scene's textures and programs in */
  constructor(gl) {
    this.gl = gl;
    this.drawings = [];
    this._fileTextures = new Map(); // Decoration textures by file, uploaded once and reused across scene switches
    this.seaweedShader = compileProgram(gl, SEAWEED_TRANSFORM);
    this.fishShader = compileProgram(gl, FISH_TRANSFORM);
    this.bubbleTexture = this.loadTexture("bubble.png");
    this.backgrounds = [
      { type: "complex", name: "Ocean" },
      { type: "simple", name: "Scene 2", background: "scene2.jpg" },
      { type: "simple", name: "Scene 3", background: "scene3.webp" },
    ];
    this.backgroundIndex = 0;
    this.scans = new Map(); // Every fish's {image, extent} by photo name, so a disabled fish can come back
    this.swimming = new Map(); // Fish in the tank by photo name; leaving fish are not here
    this.updateBackground();
  }

  /**
   * A decoration's texture, transparent until its image arrives
   * @param {string} name Image file name in ocean/images
   * @returns {WebGLTexture} The texture, the same one for every call with this name
   */
  loadTexture(name) {
    if (!this._fileTextures.has(name)) {
      const texture = createTexture(this.gl, NOT_LOADED);
      this._fileTextures.set(name, texture);
      loadImage(IMAGES_URL + name).then(
        (image) => fillTexture(this.gl, texture, image),
        (error) => console.error(`Cannot load ${name}: ${error}`), // It stays transparent; the tank carries on
      );
    }
    return this._fileTextures.get(name);
  }

  switchBackground(step) {
    this.backgroundIndex = mod(this.backgroundIndex + step, this.backgrounds.length);
    this.updateBackground();
  }

  /** Rebuild the decorative sprites for the current background, keeping the fish */
  updateBackground() {
    this.drawings = this.drawings.filter((drawing) => drawing instanceof DrawingFish);
    const config = this.backgrounds[this.backgroundIndex];
    if (config.type === "complex") {
      this.drawComplexOcean();
    } else {
      // simple scene
      this.drawings.push(this.createBackLayer(config.background, -0.8));
    }
  }

  /**
   * Create sprite for the scene background
   * @param {string} filename Background image name in ocean/images
   * @param {number} z Depth position of the sprite
   * @returns {DrawingStatic} Sprite object for the background
   */
  createBackLayer(filename, z) {
    const drawingBack = new DrawingStatic(this.loadTexture(filename));
    drawingBack.position = [0, 0.0, z];
    drawingBack.scale = [...BACKGROUND_SCALE];
    return drawingBack;
  }

  addSeaweed(texture, position, scale, color = null) {
    const drawing = new DrawingSeaweed(texture, { shader: this.seaweedShader });
    drawing.position = [...position];
    drawing.scale = [...scale];
    if (color !== null) {
      drawing.color = [...color];
    }
    this.drawings.push(drawing);
  }

  /** Support function to draw sails */
  drawSails() {
    this.addSeaweed(this.loadTexture("sail_1.png"), [1.2, -0.43, -0.77], [0.6, 0.4, 1.0]);
    this.addSeaweed(this.loadTexture("sail_2.png"), [1.6, -0.34, -0.77], [0.3, 0.5, 1.0]);
    this.addSeaweed(this.loadTexture("sail_3.png"), [1.7, -0.71, -0.77], [0.2, 0.3, 1.0]);
  }

  /** Draw the complex ocean scene with all decorative elements */
  drawComplexOcean() {
    for (const image of ["back_down.png", "back_middle.png", "back_reef.png"]) {
      this.drawings.push(this.createBackLayer(image, -0.8));
    }

    this.drawSails();

    for (const image of ["seaweed_2.png", "seaweed_1.png", "seaweed_3.png"]) {
      const texture = this.loadTexture(image);
      // Draw seaweed under the ship
      this.addSeaweed(texture, [1.2, 0.4, -0.75], [0.8, 0.4, 1.0]);
      // Draw seaweed in the right corner
      this.addSeaweed(texture, [1.2, 1.0, 0.9], [0.8, 1.4, 1.0]);
      // Draw seaweed in the front of the rock
      this.addSeaweed(texture, [0.2, 0.15, -0.7], [0.4, 0.4, 1.0]);
      // Draw seaweed in the left corner
      this.addSeaweed(texture, [-1.2, 0.6, 0.9], [0.3, 1.0, 1.0]);
      // Draw seaweed on the background
      this.addSeaweed(texture, [-0.8, -0.8, -0.795], [0.3, 1.2, 1.0], [0.3, 0.3, 0.8]);
      this.addSeaweed(texture, [0.0, -0.2, -0.795], [-0.3, 1.0, 1.0]);
      this.addSeaweed(texture, [-0.4, -0.2, -0.795], [0.1, 0.3, 1.0]);
    }
  }

  addFish(name) {
    const { image, extent } = this.scans.get(name);
    const fish = new DrawingFish(createTexture(this.gl, image), {
      shader: this.fishShader,
      bubbleTexture: this.bubbleTexture,
      extent,
    });
    this.drawings.push(fish);
    this.swimming.set(name, fish);
  }

  /**
   * Send away the fish that are no longer enabled and add enabled fish that are not in the tank yet
   * @param {string[]} enabled Photo names of the enabled fish; a name whose image has not arrived yet waits
   */
  follow(enabled) {
    const wanted = new Set(enabled);
    for (const name of [...this.swimming.keys()].filter((swimming) => !wanted.has(swimming))) {
      this.swimming.get(name).goAway();
      this.swimming.delete(name);
    }
    for (const name of enabled) {
      if (!this.swimming.has(name) && this.scans.has(name)) {
        this.addFish(name);
      }
    }
  }

  removeDeadFish() {
    const dead = this.drawings.filter((drawing) => drawing instanceof DrawingFish && !drawing.isAlive);
    this.drawings = this.drawings.filter((drawing) => !dead.includes(drawing));
    for (const fish of dead) {
      this.gl.deleteTexture(fish.texture);
    }
  }
}
