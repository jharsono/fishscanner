// The sprite and camera matrices, independent of WebGL.
import { columnMajor, modelMatrix, orthographic } from "/tank/engine/matrices.js";
import { assert, assertAllClose, test } from "./check.js";

function apply(m, [x, y, z]) {
  const point = [x, y, z, 1.0];
  const result = [0, 1, 2, 3].map((row) => point.reduce((sum, value, col) => sum + m[row * 4 + col] * value, 0));
  return result.slice(0, 3).map((value) => value / result[3]);
}

const IDENTITY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];

test("identity at defaults", () => {
  assertAllClose(modelMatrix([0, 0, 0], [0, 0, 0], [1, 1, 1]), IDENTITY);
});

test("translation then scale", () => {
  const m = modelMatrix([1.0, 2.0, 3.0], [0, 0, 0], [2.0, 3.0, 4.0]);
  assertAllClose(apply(m, [0.5, 0.5, 0.5]), [2.0, 3.5, 5.0]);
});

test("rotation about y turns x towards minus z", () => {
  const m = modelMatrix([0, 0, 0], [0.0, 90.0, 0.0], [1, 1, 1]);
  assertAllClose(apply(m, [1.0, 0.0, 0.0]), [0.0, 0.0, -1.0], { atol: 1e-6 });
});

test("rotation of 180 about y mirrors x: a fish turning around must flip exactly", () => {
  const m = modelMatrix([0, 0, 0], [0.0, 180.0, 0.0], [1, 1, 1]);
  assertAllClose(apply(m, [0.5, 0.25, 0.0]), [-0.5, 0.25, 0.0], { atol: 1e-6 });
});

test("orthographic maps corners to clip space, smaller y higher on screen", () => {
  const aspect = 800 / 600;
  const p = orthographic(-aspect, aspect, 1, -1, -1, 1);
  assertAllClose(apply(p, [-aspect, 1.0, 0.0]), [-1.0, -1.0, 0.0]);
  assertAllClose(apply(p, [aspect, -1.0, 0.0]), [1.0, 1.0, 0.0]);
  assert(apply(p, [0.0, -0.7, 0.0])[1] > apply(p, [0.0, 0.3, 0.0])[1]);
});

test("column-major layout puts a translation in the last four numbers, as WebGL expects", () => {
  const laidOut = columnMajor(modelMatrix([1.0, 2.0, 3.0], [0, 0, 0], [1, 1, 1]));
  assert(laidOut instanceof Float32Array);
  assertAllClose(Array.from(laidOut), [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 1, 2, 3, 1]);
});
