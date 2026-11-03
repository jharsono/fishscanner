"""Row-major 4x4 float32 matrices for sprite transforms and the camera."""

import numpy as np


def translation(offset: np.ndarray) -> np.ndarray:
    m = np.identity(4, dtype=np.float32)
    m[:3, 3] = offset
    return m


def scaling(factors: np.ndarray) -> np.ndarray:
    m = np.identity(4, dtype=np.float32)
    m[0, 0], m[1, 1], m[2, 2] = factors
    return m


def rotation(axis: int, degrees: float) -> np.ndarray:
    """Rotation about one of the coordinate axes (0 = x, 1 = y, 2 = z)."""
    radians = np.radians(degrees)
    c, s = np.cos(radians), np.sin(radians)
    m = np.identity(4, dtype=np.float32)
    a, b = [(1, 2), (2, 0), (0, 1)][axis]
    m[a, a], m[a, b] = c, -s
    m[b, a], m[b, b] = s, c
    return m


def model_matrix(position: np.ndarray, rotate: np.ndarray, scale: np.ndarray) -> np.ndarray:
    """Translate, then rotate about x, y and z, then scale, matching the legacy transform order."""
    return (
        translation(position)
        @ rotation(0, rotate[0])
        @ rotation(1, rotate[1])
        @ rotation(2, rotate[2])
        @ scaling(scale)
    )


def orthographic(left: float, right: float, bottom: float, top: float, near: float, far: float) -> np.ndarray:
    m = np.identity(4, dtype=np.float32)
    m[0, 0] = 2 / (right - left)
    m[1, 1] = 2 / (top - bottom)
    m[2, 2] = -2 / (far - near)
    m[0, 3] = -(right + left) / (right - left)
    m[1, 3] = -(top + bottom) / (top - bottom)
    m[2, 3] = -(far + near) / (far - near)
    return m
