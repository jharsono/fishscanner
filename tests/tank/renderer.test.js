// Rendering through real WebGL into an offscreen canvas. A port of the GL tests in tests/test_renderer.py.
import { CONTEXT_ATTRIBUTES, createTexture, loadImage, Renderer } from "/tank/engine/renderer.js";
import { compileProgram } from "/tank/engine/shaders.js";
import { DrawingBubble } from "/tank/ocean/drawingbubble.js";
import { DrawingFish, FISH_TRANSFORM } from "/tank/ocean/drawingfish.js";
import { SEAWEED_TRANSFORM } from "/tank/ocean/drawingseaweed.js";
import { DrawingStatic } from "/tank/ocean/drawingstatic.js";
import { assert, assertClose, test } from "./check.js";

const WIDTH = 800;
const HEIGHT = 600;
const CLEAR = [26, 26, 51]; // The clear colour (0.1, 0.1, 0.2)

// One context for the file: Chrome starts dropping the oldest after a dozen or so, with a warning
const canvas = document.createElement("canvas");
canvas.width = WIDTH;
canvas.height = HEIGHT;
const gl = canvas.getContext("webgl", CONTEXT_ATTRIBUTES);

function newRenderer() {
  return new Renderer(gl, WIDTH, HEIGHT);
}

function readPixel(x, y) {
  const pixel = new Uint8Array(4);
  gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, pixel);
  return Array.from(pixel);
}

function readFrame() {
  const frame = new Uint8Array(WIDTH * HEIGHT * 4);
  gl.readPixels(0, 0, WIDTH, HEIGHT, gl.RGBA, gl.UNSIGNED_BYTE, frame);
  return frame;
}

function same(a, b) {
  return a.length === b.length && a.every((value, i) => value === b[i]);
}

function solidTexture(rgba) {
  return createTexture(gl, new ImageData(new Uint8ClampedArray([...rgba, ...rgba, ...rgba, ...rgba]), 2, 2));
}

function fullScreenSprite(texture) {
  const sprite = new DrawingStatic(texture);
  sprite.scale = [3.6, 2.0, 1.0];
  return sprite;
}

/** Bounding box [x0, x1, y0, y1] of pixels that differ from the clear colour */
function silhouetteBox(frame) {
  let [x0, x1, y0, y1] = [Infinity, -Infinity, Infinity, -Infinity];
  for (let y = 0; y < HEIGHT; y++) {
    for (let x = 0; x < WIDTH; x++) {
      const i = (y * WIDTH + x) * 4;
      if (frame[i] !== CLEAR[0] || frame[i + 1] !== CLEAR[1] || frame[i + 2] !== CLEAR[2]) {
        x0 = Math.min(x0, x);
        x1 = Math.max(x1, x);
        y0 = Math.min(y0, y);
        y1 = Math.max(y1, y);
      }
    }
  }
  return [x0, x1, y0, y1];
}

function toClip(renderer, x, y) {
  const p = renderer.projection;
  return [0, 1].map((row) => p[row * 4] * x + p[row * 4 + 1] * y + p[row * 4 + 3]);
}

test("a sprite covers the view", () => {
  newRenderer().render([fullScreenSprite(solidTexture([255, 0, 0, 255]))]);
  assert(same(readPixel(WIDTH / 2, HEIGHT / 2), [255, 0, 0, 255]));
  assert(same(readPixel(1, 1), [255, 0, 0, 255]));
});

test("a sprite's colour tints its texture", () => {
  const sprite = fullScreenSprite(solidTexture([255, 255, 255, 255]));
  sprite.color = [0.0, 1.0, 0.0];
  newRenderer().render([sprite]);
  assert(same(readPixel(WIDTH / 2, HEIGHT / 2), [0, 255, 0, 255]));
});

test("transparent texels are discarded", () => {
  newRenderer().render([fullScreenSprite(solidTexture([255, 0, 0, 0]))]);
  assert(same(readPixel(WIDTH / 2, HEIGHT / 2).slice(0, 3), CLEAR));
});

test("a texture keeps an image's own values, ignoring its colour profile, as the desktop app does", async () => {
  // adobe_rgb.png: 2x2 pixels of (26, 173, 253), the backgrounds' open water, saved with the Adobe
  // RGB (1998) profile the background images carry. Converted to sRGB, its red would drop to about 0.
  const sprite = fullScreenSprite(createTexture(gl, await loadImage("/tests/tank/adobe_rgb.png")));
  newRenderer().render([sprite]);
  const drawn = readPixel(WIDTH / 2, HEIGHT / 2);
  assert(same(drawn, [26, 173, 253, 255]), `drawn as ${drawn}`);
});

test("the nearer sprite wins the depth test", () => {
  const back = fullScreenSprite(solidTexture([255, 0, 0, 255]));
  back.position = [0.0, 0.0, -0.8];
  const front = fullScreenSprite(solidTexture([0, 0, 255, 255]));
  front.position = [0.0, 0.0, 0.5];
  newRenderer().render([front, back]);
  assert(same(readPixel(WIDTH / 2, HEIGHT / 2), [0, 0, 255, 255]));
});

test("smaller y is higher on screen", () => {
  const sprite = new DrawingStatic(solidTexture([255, 0, 0, 255]));
  sprite.position = [0.0, -0.5, 0.0]; // Upper half in world space
  sprite.scale = [3.6, 1.0, 1.0];
  newRenderer().render([sprite]);
  assert(same(readPixel(WIDTH / 2, HEIGHT - 2).slice(0, 3), [255, 0, 0]), "GL rows start at the bottom");
  assert(!same(readPixel(WIDTH / 2, 2).slice(0, 3), [255, 0, 0]));
});

for (const [name, transform] of [
  ["fish", FISH_TRANSFORM],
  ["seaweed", SEAWEED_TRANSFORM],
]) {
  test(`the ${name} shader compiles and renders`, () => {
    const sprite = fullScreenSprite(solidTexture([0, 255, 0, 255]));
    sprite._shader = compileProgram(gl, transform);
    newRenderer().render([sprite]);
    assert(same(readPixel(WIDTH / 2, HEIGHT / 2), [0, 255, 0, 255]));
    gl.deleteProgram(sprite._shader.program);
    assert(gl.getError() === gl.NO_ERROR);
  });
}

test("resize updates the viewport and the projection", () => {
  const renderer = newRenderer();
  renderer.resize(1600, 600);
  assert(same(Array.from(gl.getParameter(gl.VIEWPORT)), [0, 0, 1600, 600]));
  const aspect = 1600 / 600;
  assertClose(toClip(renderer, aspect, 0.0)[0], 1.0); // Wider world, right edge on the window edge
  assertClose(toClip(renderer, 0.0, 1.0)[1], -1.0); // Full height still visible (world y points down)
  renderer.resize(WIDTH, HEIGHT);
});

test("a wide window crops the height beyond the maximum aspect", () => {
  const renderer = new Renderer(gl, WIDTH, HEIGHT, 1.8);
  renderer.resize(1600, 600); // Aspect 2.67, wider than the backgrounds
  assertClose(toClip(renderer, 1.8, 0.0)[0], 1.0); // Background edge lands on the window edge
  assertClose(toClip(renderer, 0.0, 1.8 / (1600 / 600))[1], -1.0); // Only the middle band of height is shown
  renderer.resize(800, 600); // Aspect 1.33 is under the limit: unchanged behaviour
  assertClose(toClip(renderer, 800 / 600, 1.0)[0], 1.0);
  assertClose(toClip(renderer, 0.0, 1.0)[1], -1.0);
});

test("bubbles attached to a fish are drawn", async () => {
  const renderer = newRenderer();
  const fish = new DrawingFish(solidTexture([255, 0, 0, 255]));
  fish.position = [-1.0, 0.8, 0.0]; // Out of the way, bottom left
  fish.scale = [0.1, 0.1, 1.0];
  renderer.render([fish]);
  const withoutBubble = readFrame();

  const bubble = new DrawingBubble(createTexture(gl, await loadImage("/images/bubble.png")), {
    startX: 0.0,
    startY: 0.0,
  });
  bubble.scale = [0.5, 0.5, 1.0];
  fish._bubbles.push(bubble);
  renderer.render([fish]);
  const frame = readFrame();
  let changed = 0;
  for (let i = 0; i < frame.length; i += 4) {
    if (frame[i] !== withoutBubble[i] || frame[i + 1] !== withoutBubble[i + 1] || frame[i + 2] !== withoutBubble[i + 2]) {
      changed += 1;
    }
  }
  assert(changed > 1000, `the bubble left only ${changed} visible pixels`);
});

test("a near fish is drawn in front of a far fish", () => {
  const renderer = newRenderer();
  const near = new DrawingFish(solidTexture([255, 0, 0, 255]));
  const far = new DrawingFish(solidTexture([0, 0, 255, 255]));
  for (const fish of [near, far]) {
    fish.position = [0.0, 0.0, 0.0];
    fish.scale = [1.0, 0.75, 0.3];
  }
  far.position[2] = -0.5;
  for (const order of [
    [near, far],
    [far, near],
  ]) {
    renderer.render(order);
    assert(same(readPixel(WIDTH / 2, HEIGHT / 2).slice(0, 3), [255, 0, 0]), "far fish drawn on top");
  }
});

test("the fish's tail beat foreshortens its width but never moves its height", () => {
  const renderer = newRenderer();
  const fish = new DrawingFish(solidTexture([255, 0, 0, 255]), { shader: compileProgram(gl, FISH_TRANSFORM) });
  fish.position = [0.0, 0.0, 0.0];
  fish.scale = [1.0, 0.5, 1.0];
  fish.shaderParams[1] = 0.6; // Peak swing
  const boxes = [];
  for (let i = 0; i < 7; i++) {
    fish.shaderParams[0] = (2 * Math.PI * i) / 6; // One beat
    renderer.render([fish]);
    boxes.push(silhouetteBox(readFrame()));
  }
  const heights = new Set(boxes.map(([, , y0, y1]) => y1 - y0));
  const widths = new Set(boxes.map(([x0, x1]) => x1 - x0));
  assert(heights.size === 1, `the beat must not move the fish vertically: ${[...heights]}`);
  assert(widths.size > 1, "the tail must foreshorten over the beat");
});

test("the head turn foreshortens the head end only", () => {
  const renderer = newRenderer();
  const fish = new DrawingFish(solidTexture([255, 0, 0, 255]), { shader: compileProgram(gl, FISH_TRANSFORM) });
  fish.position = [0.0, 0.0, 0.0];
  fish.scale = [1.0, 0.5, 1.0];
  fish.shaderParams = [0.0, 0.0, 0.0, 0.0];
  renderer.render([fish]);
  const [x0, x1, y0, y1] = silhouetteBox(readFrame());
  fish.shaderParams[2] = 0.5; // Head turned
  renderer.render([fish]);
  const [tx0, tx1, ty0, ty1] = silhouetteBox(readFrame());
  assert(ty0 === y0 && ty1 === y1, "never vertical");
  assert(tx0 === x0, "the tail end (-x, left on screen) does not move");
  assert(tx1 < x1, "the head end pulls in");
});
