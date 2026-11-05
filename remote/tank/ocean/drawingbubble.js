import { Drawing } from "../engine/drawing.js";
import { uniform } from "../engine/random.js";

/** Sprite for drawing of bubble */
export class DrawingBubble extends Drawing {
  /**
   * Set starting position for the bubble
   * @param {WebGLTexture|null} texture Bubble texture
   * @param {{startX?: number, startY?: number}} start Start position of the bubble
   */
  constructor(texture, { startX = 0.0, startY = 0.0 } = {}) {
    super(texture, { gridX: 1, gridY: 1 });
    this.isTransparent = true; // Bubble texture has soft alpha edges

    const bubbleSize = uniform(0.01, 0.15);
    this.scale = [bubbleSize, bubbleSize, 1.0];
    this.position = [startX, startY, 0.0];
    this._startX = startX;
    this._startY = startY;

    this.speedY = -0.005;
    this.frequencyX = 10;
    this.deviationX = 0.1;
  }

  /** Logic of movement of the bubble */
  animation() {
    this.position[0] = this._startX + this.deviationX * Math.sin(this.position[1] * this.frequencyX);
    this.position[1] += this.speedY;
  }
}
