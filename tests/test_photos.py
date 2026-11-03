"""Tests for photo discovery, loading, scanning and directory watching."""

import shutil
import time
from pathlib import Path
from queue import Queue

import cv2
import numpy as np
import pytest
from PIL import Image
from pillow_heif import register_heif_opener

from engine.photos import PhotoWatcher, list_photos, scan_photo_file
from engine.simplescanner import SimpleScanner
from tests.scanner_fixtures import EXAMPLES, PHOTOS, golden_path

register_heif_opener()

EXAMPLE = PHOTOS / EXAMPLES[0]


@pytest.fixture(scope="module")
def scanner() -> SimpleScanner:
    return SimpleScanner()


@pytest.fixture
def golden_alpha() -> np.ndarray:
    golden = cv2.imread(str(golden_path(EXAMPLES[0])), cv2.IMREAD_GRAYSCALE)
    assert golden is not None
    return golden


def test_list_photos_is_case_insensitive_and_sorted(tmp_path: Path):
    for name in ["b.JPG", "a.jpg", "c.jpeg", "D.HEIC", "e.png", "notes.txt"]:
        (tmp_path / name).write_bytes(b"x")
    (tmp_path / "sub").mkdir()
    assert [p.name for p in list_photos(tmp_path)] == ["D.HEIC", "a.jpg", "b.JPG", "c.jpeg"]


def test_scan_jpg_matches_golden(scanner, tmp_path: Path, golden_alpha):
    photo = tmp_path / "IMG_0001.JPG"
    shutil.copy(EXAMPLE, photo)
    fish = scan_photo_file(photo, scanner)
    assert fish is not None
    assert fish.shape == (600, 800, 4)
    assert int((fish[..., 3] != golden_alpha).sum()) == 0


def test_scan_heic(scanner, tmp_path: Path, golden_alpha):
    photo = tmp_path / "IMG_0002.heic"
    Image.open(EXAMPLE).save(photo, format="HEIF", quality=90)
    fish = scan_photo_file(photo, scanner)
    assert fish is not None
    assert fish.shape == (600, 800, 4)
    # HEIF re-encoding is lossy, so allow a small mask difference
    assert int((fish[..., 3] != golden_alpha).sum()) < 0.01 * golden_alpha.size


def test_scan_unreadable_file_returns_none(scanner, tmp_path: Path):
    photo = tmp_path / "broken.jpg"
    photo.write_bytes(b"not a jpeg")
    assert scan_photo_file(photo, scanner) is None


def test_scan_truncated_jpg_returns_none(scanner, tmp_path: Path):
    data = EXAMPLE.read_bytes()
    truncated = tmp_path / "truncated.jpg"
    truncated.write_bytes(data[: len(data) // 2])
    assert scan_photo_file(truncated, scanner) is None


def test_scan_photo_without_markers_returns_none(scanner, tmp_path: Path):
    photo = tmp_path / "blank.jpg"
    cv2.imwrite(str(photo), np.full((600, 800, 3), 255, dtype=np.uint8))
    assert scan_photo_file(photo, scanner) is None


def drain(queue: Queue) -> list:
    items = []
    while not queue.empty():
        items.append(queue.get())
    return items


def wait_for(queue: Queue, count: int, timeout: float) -> None:
    deadline = time.monotonic() + timeout
    while queue.qsize() < count and time.monotonic() < deadline:
        time.sleep(0.05)


def test_watcher_scans_a_file_once_it_stops_growing(scanner, tmp_path: Path, golden_alpha):
    queue: Queue = Queue()
    watcher = PhotoWatcher(tmp_path, scanner, queue, poll_interval=0.1, settle_time=0.5)
    watcher.start()
    try:
        data = EXAMPLE.read_bytes()
        target = tmp_path / "IMG_0003.jpg"
        chunk = len(data) // 4 + 1
        with target.open("wb") as f:
            for start in range(0, len(data), chunk):
                f.write(data[start : start + chunk])
                f.flush()
                time.sleep(0.25)  # longer than poll_interval, so the watcher sees it growing
        wait_for(queue, 1, timeout=5)
        time.sleep(0.5)  # give a buggy watcher time to emit a duplicate
    finally:
        watcher.stop()
    fish = drain(queue)
    assert len(fish) == 1
    assert int((fish[0][..., 3] != golden_alpha).sum()) == 0


def test_watcher_ignores_files_present_at_start(scanner, tmp_path: Path):
    shutil.copy(EXAMPLE, tmp_path / "existing.jpg")
    queue: Queue = Queue()
    watcher = PhotoWatcher(tmp_path, scanner, queue, poll_interval=0.1, settle_time=0.5)
    watcher.start()
    try:
        time.sleep(0.5)
    finally:
        watcher.stop()
    assert queue.empty()


def test_watcher_gives_up_on_unreadable_file_without_blocking(scanner, tmp_path: Path):
    queue: Queue = Queue()
    watcher = PhotoWatcher(tmp_path, scanner, queue, poll_interval=0.1, settle_time=0.5)
    watcher.start()
    try:
        (tmp_path / "broken.jpg").write_bytes(b"not a jpeg")
        time.sleep(0.5)
        shutil.copy(EXAMPLE, tmp_path / "good.jpg")
        wait_for(queue, 1, timeout=5)
    finally:
        watcher.stop()
    assert len(drain(queue)) == 1


def test_scan_truncated_heic_returns_none(scanner, tmp_path: Path):
    full = tmp_path / "full.heic"
    Image.open(EXAMPLE).save(full, format="HEIF", quality=90)
    data = full.read_bytes()
    truncated = tmp_path / "truncated.heic"
    truncated.write_bytes(data[: len(data) // 2])
    assert scan_photo_file(truncated, scanner) is None


def test_watcher_retries_a_copy_that_stalls_longer_than_settle_time(scanner, tmp_path: Path, golden_alpha):
    queue: Queue = Queue()
    watcher = PhotoWatcher(tmp_path, scanner, queue, poll_interval=0.1, settle_time=0.3)
    watcher.start()
    try:
        data = EXAMPLE.read_bytes()
        target = tmp_path / "stalled.jpg"
        with target.open("wb") as f:
            f.write(data[: len(data) // 2])
            f.flush()
            time.sleep(1.0)  # stall longer than settle_time: the half file looks finished
            f.write(data[len(data) // 2 :])
        wait_for(queue, 1, timeout=10)
        time.sleep(0.5)
    finally:
        watcher.stop()
    fish = drain(queue)
    assert len(fish) == 1
    assert int((fish[0][..., 3] != golden_alpha).sum()) == 0


def test_watcher_survives_a_truncated_heic_and_keeps_scanning(scanner, tmp_path: Path):
    full = tmp_path / "full.heic"
    Image.open(EXAMPLE).save(full, format="HEIF", quality=90)
    data = full.read_bytes()
    full.unlink()
    queue: Queue = Queue()
    watcher = PhotoWatcher(tmp_path, scanner, queue, poll_interval=0.1, settle_time=0.2)
    watcher.start()
    try:
        (tmp_path / "truncated.heic").write_bytes(data[: len(data) // 2])
        time.sleep(1.0)
        shutil.copy(EXAMPLE, tmp_path / "good.jpg")
        wait_for(queue, 1, timeout=10)
    finally:
        watcher.stop()
    assert len(drain(queue)) == 1


def test_watcher_stop_before_start_is_harmless(scanner, tmp_path: Path):
    PhotoWatcher(tmp_path, scanner, Queue()).stop()


def test_watcher_survives_the_folder_being_removed_and_recreated(scanner, tmp_path: Path):
    photos = tmp_path / "photos"
    photos.mkdir()
    queue: Queue = Queue()
    watcher = PhotoWatcher(photos, scanner, queue, poll_interval=0.1, settle_time=0.2)
    watcher.start()
    try:
        shutil.rmtree(photos)
        time.sleep(0.3)
        photos.mkdir()
        shutil.copy(EXAMPLE, photos / "after.jpg")
        wait_for(queue, 1, timeout=10)
    finally:
        watcher.stop()
    assert len(drain(queue)) == 1
