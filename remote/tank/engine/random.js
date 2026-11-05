// Seedable random numbers in the shapes the sprites use, standing in for numpy.random: tests seed
// it for repeatable fish, and otherwise it starts from a seed drawn from Math.random.

let state = 0;

export function seed(value) {
  state = value >>> 0;
}

// mulberry32: a small 32-bit generator, plenty for animation
function next() {
  state = (state + 0x6d2b79f5) >>> 0;
  let t = state;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

/** A number in [low, high) */
export function uniform(low, high) {
  return low + (high - low) * next();
}

/** An integer in [low, high), or in [0, low) when high is left out, like numpy.random.randint */
export function randint(low, high) {
  if (high === undefined) {
    return Math.floor(next() * low);
  }
  return low + Math.floor(next() * (high - low));
}

/** One of items: evenly, or with the given probabilities (which sum to 1) */
export function choice(items, probabilities) {
  if (probabilities === undefined) {
    return items[randint(items.length)];
  }
  let remaining = next();
  for (let i = 0; i < items.length - 1; i++) {
    remaining -= probabilities[i];
    if (remaining < 0) {
      return items[i];
    }
  }
  return items[items.length - 1];
}

seed(Math.floor(Math.random() * 4294967296));
