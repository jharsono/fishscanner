"""Shared paths and helpers for scanner tests and golden regeneration."""
from pathlib import Path

import cv2
import numpy as np

from engine.simplescanner import SimpleScanner

REPO = Path(__file__).resolve().parent.parent
PHOTOS = REPO / "photos"
GOLDEN = REPO / "tests" / "golden"
EXAMPLES = ["example_fish1.jpg", "example_fish2.jpg"]


def golden_path(name: str) -> Path:
    return GOLDEN / f"{Path(name).stem}_alpha.png"


def read_photo(path: Path) -> np.ndarray:
    """Load a photo as RGB, the colour order the scanner expects."""
    frame = cv2.imread(str(path))
    assert frame is not None, f"could not read {path}"
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


def scan_photo(scanner: SimpleScanner, path: Path) -> np.ndarray:
    return scanner.remove_background(scanner.scan(read_photo(path)))
