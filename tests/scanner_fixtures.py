"""Shared paths and helpers for scanner tests and golden regeneration."""

from pathlib import Path

import numpy as np

from engine.photos import read_photo as _read_photo
from engine.simplescanner import SimpleScanner

REPO = Path(__file__).resolve().parent.parent
PHOTOS = REPO / "photos"
GOLDEN = REPO / "tests" / "golden"
EXAMPLES = ["example_fish1.jpg", "example_fish2.jpg"]


def golden_path(name: str) -> Path:
    return GOLDEN / f"{Path(name).stem}_alpha.png"


def read_photo(path: Path) -> np.ndarray:
    """Load a photo exactly as the app does, failing loudly if it cannot be decoded."""
    frame = _read_photo(path)
    assert frame is not None, f"could not read {path}"
    return frame


def scan_photo(scanner: SimpleScanner, path: Path) -> np.ndarray:
    return scanner.remove_background(scanner.scan(read_photo(path)))
