// A test registry and assertions for the tank's JavaScript. tests/test_tank.py loads runner.html in
// headless Chrome, imports one *.test.js file, and calls runRegistered() for its results.

const registered = [];

export function test(name, body) {
  registered.push({ name, body });
}

export async function runRegistered() {
  const results = [];
  for (const { name, body } of registered) {
    try {
      await body();
      results.push({ name, error: null });
    } catch (error) {
      results.push({ name, error: error.stack || String(error) });
    }
  }
  return results;
}

export function assert(condition, message = "assertion failed") {
  if (!condition) {
    throw new Error(message);
  }
}

// numpy.isclose's rule and defaults, so tolerances ported from the Python tests (tag desktop-final) mean the same thing
export function isClose(actual, expected, { rtol = 1e-5, atol = 1e-8 } = {}) {
  return Math.abs(actual - expected) <= atol + rtol * Math.abs(expected);
}

export function assertClose(actual, expected, tolerance = {}) {
  assert(isClose(actual, expected, tolerance), `${actual} is not close to ${expected}`);
}

export function assertAllClose(actual, expected, tolerance = {}) {
  assert(
    actual.length === expected.length && actual.every((value, i) => isClose(value, expected[i], tolerance)),
    `[${actual}] is not close to [${expected}]`,
  );
}
