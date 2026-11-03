"""Regression tests for SimpleScanner against real example photos.

These cover the alpha mask only; the RGB content of opaque pixels is not
checked. Golden alpha masks live in tests/golden/. Regenerate them
deliberately with tests/make_golden.py only when a scanner change is meant to
alter the mask.
"""

import cv2
import numpy as np
import pytest

from engine.simplescanner import SimpleScanner
from tests.scanner_fixtures import EXAMPLES, PHOTOS, golden_path, read_photo, scan_photo

# The pipeline is bit-exact deterministic on one machine (0 differing pixels
# on rerun and on regeneration), so no tolerance is justified yet. Raise this
# only after measuring an actual cross-platform difference in CI and record
# that number here.
MAX_DIFFERING_PIXELS = 0


@pytest.fixture(scope="module")
def scanner() -> SimpleScanner:
    return SimpleScanner()


@pytest.mark.parametrize("name", EXAMPLES)
def test_output_is_rgba_at_target_size(scanner, name):
    out = scan_photo(scanner, PHOTOS / name)
    assert out.shape == (scanner.target_h, scanner.target_w, 4)
    assert out.dtype == np.uint8


@pytest.mark.parametrize("name", EXAMPLES)
def test_alpha_mask_matches_golden(scanner, name):
    out = scan_photo(scanner, PHOTOS / name)
    golden = cv2.imread(str(golden_path(name)), cv2.IMREAD_GRAYSCALE)
    assert golden is not None, "golden mask missing; run tests/make_golden.py"
    differing = int((out[..., 3] != golden).sum())
    assert differing <= MAX_DIFFERING_PIXELS, f"{differing} pixels differ from golden"


@pytest.mark.parametrize("name", EXAMPLES)
def test_transparent_pixels_are_fully_zeroed(scanner, name):
    out = scan_photo(scanner, PHOTOS / name)
    assert not out[out[..., 3] == 0].any()


def test_blank_image_raises(scanner):
    blank = np.full((600, 800, 3), 255, dtype=np.uint8)
    with pytest.raises(ValueError):
        scanner.scan(blank)


def test_photo_with_one_marker_hidden_raises(scanner):
    """Three of four markers is not enough: the top-left one is painted over."""
    frame = read_photo(PHOTOS / EXAMPLES[0])
    corners, ids, _ = scanner._aruco_detector.detectMarkers(frame)
    assert ids is not None and len(ids) == 4, "fixture must contain all four markers"
    top_left = corners[list(ids.flatten()).index(scanner._marker_top_left_id)].reshape(4, 2)
    x0, y0 = top_left.min(axis=0).astype(int)
    x1, y1 = top_left.max(axis=0).astype(int)
    frame[y0:y1, x0:x1] = 255
    with pytest.raises(ValueError):
        scanner.scan(frame)


def painted_pixels(scanner: SimpleScanner, aligned: np.ndarray) -> np.ndarray:
    photo = cv2.resize(aligned, (scanner.target_w, scanner.target_h))
    hsv = cv2.cvtColor(photo, cv2.COLOR_RGB2HSV)
    # Paint on white paper in the examples' lighting (paper saturation ~7)
    return (hsv[..., 1] > 7 + scanner.paint_saturation_margin) & (hsv[..., 2] > scanner.paint_min_value)


@pytest.mark.parametrize("name", EXAMPLES)
def test_painted_areas_are_never_transparent(scanner, name):
    """A filled fin must stay opaque even where its outline is cut off by the crop."""
    aligned = scanner.scan(read_photo(PHOTOS / name))
    out = scanner.remove_background(aligned)
    leaked = painted_pixels(scanner, aligned) & (out[..., 3] == 0)
    # example_fish2 keeps a 4x3 speck at the mouth edge; anything larger is a real hole
    assert int(leaked.sum()) < 50, f"{int(leaked.sum())} painted pixels are transparent"


@pytest.mark.parametrize("name", EXAMPLES)
def test_warm_colour_cast_does_not_turn_the_paper_into_paint(scanner, name):
    """Under warm light the paper itself is saturated; the mask must still be the fish, not the page."""
    aligned = scanner.scan(read_photo(PHOTOS / name))
    cast = aligned.copy()
    cast[..., 2] = (cast[..., 2] * 0.7).astype(np.uint8)  # 30% blue deficit
    golden = cv2.imread(str(golden_path(name)), cv2.IMREAD_GRAYSCALE)
    assert golden is not None
    golden = golden > 127
    mask = scanner.remove_background(cast)[..., 3] > 127
    iou = np.logical_and(mask, golden).sum() / np.logical_or(mask, golden).sum()
    assert iou > 0.99, f"mask IoU against the golden fell to {iou:.3f}"
