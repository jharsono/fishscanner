"""Discover, load and scan fish photos, and watch a directory for new ones."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from pathlib import Path
from queue import Queue

import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

from engine.simplescanner import SimpleScanner

register_heif_opener()

PHOTO_SUFFIXES = {".jpg", ".jpeg", ".heic"}


def is_photo(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in PHOTO_SUFFIXES


def list_photos(directory: Path) -> list[Path]:
    return sorted(path for path in directory.iterdir() if is_photo(path))


def read_photo(path: Path) -> np.ndarray | None:
    """
    Load a photo as an RGB image, honouring its EXIF orientation
    :param path: JPEG or HEIC file
    :return: RGB image, or None if the file cannot be decoded or is incomplete
    """
    # Decoding goes through PIL rather than cv2.imread because PIL refuses a truncated
    # JPEG while OpenCV silently returns a partial image (a progressive JPEG cut in half
    # still decodes to a full, blurry frame with all four markers visible).
    try:
        with Image.open(path) as image:
            return np.array(ImageOps.exif_transpose(image).convert("RGB"))
    except (OSError, ValueError):
        # PIL raises UnidentifiedImageError (an OSError) for data it cannot recognise and
        # "image file is truncated" (an OSError) for an incomplete JPEG; pillow-heif raises
        # ValueError for a HEIC truncated part-way through decoding
        return None


def scan_photo_file(path: Path, scanner: SimpleScanner) -> np.ndarray | None:
    """
    Scan the fish drawing in a photo
    :param path: JPEG or HEIC file
    :param scanner: Scanner to align the drawing and remove its background
    :return: RGBA image of the fish, or None if the photo cannot be read or its markers are not found
    """
    frame = read_photo(path)
    if frame is None:
        print(f"Cannot read photo: {path}")
        return None
    try:
        aligned = scanner.scan(frame)
    except ValueError as e:
        print(f"{path}: {e}")
        return None
    return scanner.remove_background(aligned)


@dataclass
class _Pending:
    """A photo the watcher has seen but not yet scanned successfully."""

    size: int
    since: float  # When the file was first seen at this size
    attempts: int = 0
    not_before: float = 0.0  # Earliest time for the next scan attempt


class PhotoWatcher:
    """
    Scan photos that appear in a directory after start() and put the results on a queue.

    A new file is scanned only once its size has stayed the same for settle_time, so a
    photo that is still being copied in is normally never read half-written. If a scan
    still fails (a copy that stalled longer than settle_time, a truncated file, or
    markers not found) it is retried with doubling delays up to max_attempts, so a copy
    that finishes later is still picked up. After the last attempt the file is given up
    on for the rest of the session, and a file that has been scanned is not scanned
    again if it is overwritten in place. Scanning happens on a background thread; the
    queue hands (path, RGBA image) pairs to the main thread.
    """

    def __init__(
        self,
        directory: Path,
        scanner: SimpleScanner,
        output_queue: Queue,
        poll_interval: float = 0.5,
        settle_time: float = 1.0,
        max_attempts: int = 3,
    ):
        self._directory = Path(directory)
        self._scanner = scanner
        self._queue = output_queue
        self._poll_interval = poll_interval
        self._settle_time = settle_time
        self._max_attempts = max_attempts
        self._known: set[Path] = set()  # Scanned, given up on, or present when the watcher started
        self._pending: dict[Path, _Pending] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._known = set(list_photos(self._directory))
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join()

    def _run(self) -> None:
        while not self._stop.wait(self._poll_interval):
            self._poll()

    def _poll(self) -> None:
        now = time.monotonic()
        try:
            present = [path for path in list_photos(self._directory) if path not in self._known]
        except FileNotFoundError:  # The folder was removed or renamed; keep watching for it to come back
            return
        for gone in set(self._pending) - set(present):
            del self._pending[gone]
        for path in present:
            try:
                size = path.stat().st_size
            except FileNotFoundError:  # Removed between listing and stat
                continue
            pending = self._pending.setdefault(path, _Pending(size, now))
            if size != pending.size:
                self._pending[path] = _Pending(size, now)
                continue
            if now - pending.since < self._settle_time or now < pending.not_before:
                continue
            fish = scan_photo_file(path, self._scanner)
            if fish is not None:
                self._queue.put((path, fish))
                self._finish(path)
                continue
            pending.attempts += 1
            if pending.attempts >= self._max_attempts:
                print(f"Giving up on {path} after {pending.attempts} attempts")
                self._finish(path)
            else:
                pending.not_before = now + self._settle_time * 2**pending.attempts

    def _finish(self, path: Path) -> None:
        del self._pending[path]
        self._known.add(path)
