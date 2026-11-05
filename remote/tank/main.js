// The tank page: draws the fish the server lists in a canvas that fills the window, and follows
// the list as photos are added, enabled and disabled.
import { FixedStepClock } from "./engine/clock.js";
import { CONTEXT_ATTRIBUTES, loadImage, Renderer } from "./engine/renderer.js";
import { DrawingFish, preventDepthCrossings } from "./ocean/drawingfish.js";
import { BACKGROUND_SCALE, Scene } from "./ocean/scene.js";

const TICK_SECONDS = 1 / 60; // Animation step, 60 times per second
const POLL_SECONDS = 2; // How often to ask the server which fish are enabled

export class Tank {
  /**
   * @param {HTMLCanvasElement} canvas Canvas to draw in, already sized
   * @param {WebGLRenderingContext} gl Its WebGL context
   */
  constructor(canvas, gl) {
    this.canvas = canvas;
    this.renderer = new Renderer(gl, canvas.width, canvas.height, BACKGROUND_SCALE[0] / BACKGROUND_SCALE[1]);
    this.scene = new Scene(gl);
    this.enabled = []; // Names of the enabled fish in the server's latest list, oldest first
    this._loading = new Set(); // Names whose images are on their way
    this._clock = new FixedStepClock(TICK_SECONDS);
    this._lastSeconds = null;
  }

  /** One animation tick: move sprites, bring the tank in line with the enabled fish, retire dead ones */
  step() {
    preventDepthCrossings(this.scene.drawings.filter((drawing) => drawing instanceof DrawingFish));
    this.renderer.animate(this.scene.drawings);
    this.scene.follow(this.enabled);
    this.scene.removeDeadFish();
  }

  /**
   * Draw a frame, first running the animation ticks due since the last one
   * @param {number} seconds Time of this frame
   */
  frame(seconds) {
    const elapsed = this._lastSeconds === null ? 0 : seconds - this._lastSeconds;
    this._lastSeconds = seconds;
    for (let ticks = this._clock.advance(elapsed); ticks > 0; ticks--) {
      this.step();
    }
    this.renderer.render(this.scene.drawings);
  }

  /**
   * Fetch the fish list, and start loading the image of every fish not seen before (disabled ones
   * too, so enabling one later is instant). When the server cannot be reached the fish keep swimming
   * as they are, until a later poll gets through.
   */
  async poll() {
    let response;
    try {
      response = await fetch("/api/fish");
    } catch (error) {
      // fetch rejects only when no answer came: the server is restarting, or the network dropped
      console.warn(`Cannot reach the server, keeping the fish swimming: ${error}`);
      return;
    }
    if (!response.ok) {
      console.warn(`The fish list answered ${response.status}, keeping the fish swimming`);
      return;
    }
    const { fish } = await response.json();
    this.enabled = fish
      .filter((entry) => entry.enabled)
      .map((entry) => entry.name)
      .reverse(); // The list is newest first
    for (const { name, extent } of fish) {
      if (!this.scene.scans.has(name) && !this._loading.has(name)) {
        this._loading.add(name);
        loadImage(`/api/fish/${encodeURIComponent(name)}/image`)
          .then(
            (image) => this.scene.scans.set(name, { image, extent }),
            (error) => console.error(`Cannot load the fish from ${name}: ${error}`), // Tried again next poll
          )
          .finally(() => this._loading.delete(name));
      }
    }
  }
}

function toggleFullscreen() {
  const request = document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
  request.catch(() => {}); // The browser may refuse; the tank carries on in the window
}

/**
 * Draw the tank in a canvas, following the server's fish list from now on
 * @param {HTMLCanvasElement} canvas Canvas that fills the window
 * @returns {Tank|null} The running tank, or null when this browser has no WebGL
 */
export function startTank(canvas) {
  // CSS pixels rather than device pixels: a TV's GPU fills a 1080p canvas far more easily than a
  // 4K one, and the browser scales it up
  canvas.width = canvas.clientWidth;
  canvas.height = canvas.clientHeight;
  const gl = canvas.getContext("webgl", CONTEXT_ATTRIBUTES);
  if (gl === null) {
    return null;
  }
  const tank = new Tank(canvas, gl);

  window.addEventListener("resize", () => {
    canvas.width = canvas.clientWidth;
    canvas.height = canvas.clientHeight;
    tank.renderer.resize(canvas.width, canvas.height);
  });
  window.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") {
      tank.scene.switchBackground(-1);
    } else if (event.key === "ArrowRight") {
      tank.scene.switchBackground(1);
    } else if (event.key === "f" || event.key === "F") {
      toggleFullscreen();
    }
  });
  canvas.addEventListener("click", toggleFullscreen); // A TV remote's select button clicks

  const keepPolling = () => {
    tank.poll().finally(() => setTimeout(keepPolling, POLL_SECONDS * 1000));
  };
  keepPolling();

  const animate = (milliseconds) => {
    tank.frame(milliseconds / 1000);
    requestAnimationFrame(animate);
  };
  requestAnimationFrame(animate);
  return tank;
}
