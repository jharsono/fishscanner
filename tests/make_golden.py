"""Regenerate golden alpha masks from the example photos.

Run only when a scanner change is intended to alter the mask, and review the
resulting PNGs before committing them.
"""
import cv2

from engine.simplescanner import SimpleScanner
from tests.scanner_fixtures import EXAMPLES, GOLDEN, PHOTOS, golden_path, scan_photo


def main() -> None:
    GOLDEN.mkdir(exist_ok=True)
    scanner = SimpleScanner()
    for name in EXAMPLES:
        out = scan_photo(scanner, PHOTOS / name)
        cv2.imwrite(str(golden_path(name)), out[..., 3])
        print(f"wrote {golden_path(name)}")


if __name__ == "__main__":
    main()
