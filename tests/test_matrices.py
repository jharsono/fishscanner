"""Tests for the sprite and camera matrices, independent of OpenGL."""

import numpy as np

from engine.matrices import column_major, model_matrix, orthographic


def apply(matrix: np.ndarray, point: tuple[float, float, float]) -> np.ndarray:
    result = matrix @ np.array([*point, 1.0], dtype=np.float32)
    return result[:3] / result[3]


def test_identity_at_defaults():
    m = model_matrix(np.zeros(3), np.zeros(3), np.ones(3))
    assert np.allclose(m, np.identity(4))
    assert m.dtype == np.float32


def test_translation_then_scale():
    m = model_matrix(np.array([1.0, 2.0, 3.0]), np.zeros(3), np.array([2.0, 3.0, 4.0]))
    assert np.allclose(apply(m, (0.5, 0.5, 0.5)), [2.0, 3.5, 5.0])


def test_rotation_about_y_turns_x_towards_minus_z():
    m = model_matrix(np.zeros(3), np.array([0.0, 90.0, 0.0]), np.ones(3))
    assert np.allclose(apply(m, (1.0, 0.0, 0.0)), [0.0, 0.0, -1.0], atol=1e-6)


def test_rotation_of_180_about_y_mirrors_x():
    """A fish turning around is a 180 degree y rotation, which must flip x exactly."""
    m = model_matrix(np.zeros(3), np.array([0.0, 180.0, 0.0]), np.ones(3))
    assert np.allclose(apply(m, (0.5, 0.25, 0.0)), [-0.5, 0.25, 0.0], atol=1e-6)


def test_column_major_lays_out_columns_first_for_gl():
    """GLES 2.0 refuses to transpose uniforms, so matrices go up already in GL's column order."""
    m = np.arange(16, dtype=np.float32).reshape(4, 4)
    laid_out = column_major(m)
    assert list(laid_out.tobytes()) == list(m.tobytes(order="F"))
    assert laid_out.dtype == np.float32


def test_orthographic_maps_corners_to_clip_space():
    aspect = 800 / 600
    p = orthographic(-aspect, aspect, 1, -1, -1, 1)
    assert np.allclose(apply(p, (-aspect, 1.0, 0.0)), [-1.0, -1.0, 0.0])
    assert np.allclose(apply(p, (aspect, -1.0, 0.0)), [1.0, 1.0, 0.0])
    # Smaller y is higher on screen
    assert apply(p, (0.0, -0.7, 0.0))[1] > apply(p, (0.0, 0.3, 0.0))[1]
