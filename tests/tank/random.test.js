// The seedable random numbers that stand in for numpy.random.
import { choice, randint, seed, uniform } from "/tank/engine/random.js";
import { assert, test } from "./check.js";

function draws(count, draw) {
  return Array.from({ length: count }, draw);
}

test("a seed repeats the same numbers, and another seed gives others", () => {
  seed(7);
  const first = draws(5, () => uniform(0, 1));
  seed(7);
  assert(draws(5, () => uniform(0, 1)).every((value, i) => value === first[i]));
  seed(8);
  assert(draws(5, () => uniform(0, 1)).some((value, i) => value !== first[i]));
});

test("uniform stays in [low, high)", () => {
  seed(0);
  const values = draws(10000, () => uniform(0.95, 0.98));
  assert(Math.min(...values) >= 0.95 && Math.max(...values) < 0.98);
  assert(Math.max(...values) - Math.min(...values) > 0.029, "covers the range");
});

test("randint is numpy's: [low, high), or [0, n) with one argument", () => {
  seed(0);
  const ranged = new Set(draws(10000, () => randint(60, 63)));
  assert([...ranged].sort().join() === "60,61,62", `drew ${[...ranged]}`);
  const counted = new Set(draws(10000, () => randint(4)));
  assert([...counted].sort().join() === "0,1,2,3", `drew ${[...counted]}`);
});

test("choice picks evenly, or by the given probabilities", () => {
  seed(0);
  const even = draws(10000, () => choice([-1.0, 1.0]));
  const ones = even.filter((value) => value === 1.0).length;
  assert(even.every((value) => value === 1.0 || value === -1.0) && Math.abs(ones - 5000) < 300, `${ones} of 10000`);
  const weighted = draws(10000, () => choice(["rest", "cruise", "burst"], [0.3, 0.5, 0.2]));
  for (const [level, share] of [["rest", 0.3], ["cruise", 0.5], ["burst", 0.2]]) {
    const count = weighted.filter((value) => value === level).length;
    assert(Math.abs(count - share * 10000) < 300, `${level}: ${count} of 10000`);
  }
});
