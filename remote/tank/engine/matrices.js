// Row-major 4x4 matrices, as flat arrays of 16 numbers (row * 4 + column), for sprite transforms and the camera.

function identity() {
  return [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
}

function multiply(a, b) {
  const m = new Array(16).fill(0);
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 4; col++) {
      for (let k = 0; k < 4; k++) {
        m[row * 4 + col] += a[row * 4 + k] * b[k * 4 + col];
      }
    }
  }
  return m;
}

function translation([x, y, z]) {
  const m = identity();
  m[3] = x;
  m[7] = y;
  m[11] = z;
  return m;
}

function scaling([x, y, z]) {
  const m = identity();
  m[0] = x;
  m[5] = y;
  m[10] = z;
  return m;
}

/** Rotation about one of the coordinate axes (0 = x, 1 = y, 2 = z) */
function rotation(axis, degrees) {
  const radians = (degrees * Math.PI) / 180;
  const c = Math.cos(radians);
  const s = Math.sin(radians);
  const m = identity();
  const [a, b] = [[1, 2], [2, 0], [0, 1]][axis];
  m[a * 4 + a] = c;
  m[a * 4 + b] = -s;
  m[b * 4 + a] = s;
  m[b * 4 + b] = c;
  return m;
}

/** Translate, then rotate about x, y and z, then scale, matching the legacy transform order */
export function modelMatrix(position, rotate, scale) {
  return [rotation(0, rotate[0]), rotation(1, rotate[1]), rotation(2, rotate[2]), scaling(scale)].reduce(
    multiply,
    translation(position),
  );
}

export function orthographic(left, right, bottom, top, near, far) {
  const m = identity();
  m[0] = 2 / (right - left);
  m[5] = 2 / (top - bottom);
  m[10] = -2 / (far - near);
  m[3] = -(right + left) / (right - left);
  m[7] = -(top + bottom) / (top - bottom);
  m[11] = -(far + near) / (far - near);
  return m;
}

/** The matrix laid out for uniformMatrix4fv, whose transpose argument WebGL 1 only allows to be false */
export function columnMajor(m) {
  const laidOut = new Float32Array(16);
  for (let row = 0; row < 4; row++) {
    for (let col = 0; col < 4; col++) {
      laidOut[col * 4 + row] = m[row * 4 + col];
    }
  }
  return laidOut;
}
