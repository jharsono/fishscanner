// The scene: its backgrounds and the fish it keeps in line with the enabled list. Ported from the
// scene tests in tests/test_renderer.py (tag desktop-final); decoration images come from the real app's /images/.
import { CONTEXT_ATTRIBUTES, Renderer } from "/tank/engine/renderer.js";
import { DrawingFish } from "/tank/ocean/drawingfish.js";
import { Scene } from "/tank/ocean/scene.js";
import { assert, test } from "./check.js";

const canvas = document.createElement("canvas");
canvas.width = 800;
canvas.height = 600;
const gl = canvas.getContext("webgl", CONTEXT_ATTRIBUTES);

/** A scan as the server serves it: an 800x600 image with an orange patch in the middle, and its painted extent */
function fishScan() {
  const pixels = new Uint8ClampedArray(800 * 600 * 4);
  for (let y = 200; y < 400; y++) {
    for (let x = 200; x < 600; x++) {
      pixels.set([255, 128, 0, 255], (y * 800 + x) * 4);
    }
  }
  return { image: new ImageData(pixels, 800, 600), extent: [0.5, 1 / 3] };
}

function fishIn(scene) {
  return scene.drawings.filter((drawing) => drawing instanceof DrawingFish);
}

test("switching scenes does not accumulate textures", () => {
  const renderer = new Renderer(gl, 800, 600);
  const scene = new Scene(gl);
  for (let i = 0; i < scene.backgrounds.length; i++) {
    scene.switchBackground(1);
  }
  const afterOneCycle = scene._fileTextures.size;
  for (let i = 0; i < 3 * scene.backgrounds.length; i++) {
    scene.switchBackground(1);
    renderer.render(scene.drawings);
  }
  assert(scene._fileTextures.size === afterOneCycle);
});

test("switching back from the first scene wraps round to the last", () => {
  const scene = new Scene(gl);
  scene.switchBackground(-1);
  assert(scene.backgroundIndex === scene.backgrounds.length - 1, `index ${scene.backgroundIndex}`);
});

test("the scene follows the enabled fish", () => {
  const scene = new Scene(gl);
  scene.scans = new Map([
    ["a.jpg", fishScan()],
    ["b.jpg", fishScan()],
  ]);
  scene.follow(["a.jpg", "b.jpg", "c.jpg"]); // No image for c.jpg yet, so it waits
  assert([...scene.swimming.keys()].sort().join() === "a.jpg,b.jpg");
  const leaving = scene.swimming.get("a.jpg");
  scene.follow(["b.jpg"]);
  assert([...scene.swimming.keys()].join() === "b.jpg");
  assert(leaving._animationStage === "finish", "swims off rather than vanishing");
  assert(scene.drawings.includes(leaving));
  scene.follow(["b.jpg", "a.jpg"]);
  assert(scene.swimming.get("a.jpg") !== leaving, "a fresh fish swims in while the old one leaves");
  assert(fishIn(scene).length === 3);
});

test("a fish swims with its painted extent", () => {
  const scene = new Scene(gl);
  scene.scans = new Map([["a.jpg", fishScan()]]);
  scene.follow(["a.jpg"]);
  const extent = scene.swimming.get("a.jpg").extent;
  assert(extent[0] === 0.5 && extent[1] === 1 / 3, `extent ${extent}`);
});

test("a dead fish releases its texture", () => {
  const scene = new Scene(gl);
  scene.scans = new Map([["a.jpg", fishScan()]]);
  scene.follow(["a.jpg"]);
  const leaving = scene.swimming.get("a.jpg");
  assert(gl.isTexture(leaving.texture));
  scene.follow([]);
  leaving.isAlive = false;
  scene.removeDeadFish();
  assert(!scene.drawings.includes(leaving));
  assert(!gl.isTexture(leaving.texture), "the texture was not deleted");
});
