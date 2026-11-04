"""Which scanned photos swim in the tank, shared by the animation loop and the remote control."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import cv2
import numpy as np

MIN_CAP = 1
MAX_CAP = 30
THUMBNAIL_WIDTH = 240  # Pixels; enough for a phone's fish list


def thumbnail_png(scan: np.ndarray) -> bytes:
    """
    Small PNG of a scan, cropped to its painted pixels so a small drawing still fills the thumbnail
    :param scan: RGBA scan
    :return: PNG bytes with the scan's transparency
    """
    rows, cols = np.nonzero(scan[..., 3])
    if rows.size:
        scan = scan[rows.min() : rows.max() + 1, cols.min() : cols.max() + 1]
    height = max(1, round(scan.shape[0] * THUMBNAIL_WIDTH / scan.shape[1]))
    small = cv2.resize(scan, (THUMBNAIL_WIDTH, height), interpolation=cv2.INTER_AREA)
    ok, data = cv2.imencode(".png", cv2.cvtColor(small, cv2.COLOR_RGBA2BGRA))
    assert ok, "PNG encoding of a valid RGBA image cannot fail"
    return data.tobytes()


class FishRoster:
    """
    The photos that scanned into fish, which of them are enabled, and how many may swim at once.

    Enabled fish are kept oldest first; enabling one makes it the newest, and whenever there are
    more enabled fish than the cap the oldest are disabled. The cap and the disabled photos are
    saved to a JSON file so they survive a restart; photos themselves are never moved or deleted.
    The animation loop registers scans and follows enabled() while the remote control server
    changes the state from its own threads, so every method takes the lock.
    """

    def __init__(self, state_file: Path, default_cap: int):
        """
        :param state_file: JSON file holding the cap and the disabled photos
        :param default_cap: Cap to use when the state file is missing or unreadable
        """
        self._state_file = Path(state_file)
        self._lock = threading.Lock()
        self._names: list[str] = []  # Every registered photo, in registration order
        self._thumbnails: dict[str, bytes] = {}
        self._enabled: list[str] = []  # Oldest first
        self._cap, self._disabled = self._load(default_cap)

    def _load(self, default_cap: int) -> tuple[int, set[str]]:
        try:
            saved = json.loads(self._state_file.read_text())
            cap = int(saved["cap"])
            disabled = {str(name) for name in saved["disabled"]}
        except FileNotFoundError:  # First run
            return default_cap, set()
        except (OSError, ValueError, KeyError, TypeError) as e:
            # Unreadable, not JSON, or not the shape this class writes. Start fresh rather than
            # refuse to open the tank; the file is rewritten on the next change.
            print(f"Ignoring unreadable tank state in {self._state_file}: {e!r}")
            return default_cap, set()
        return max(MIN_CAP, min(MAX_CAP, cap)), disabled

    def _save(self) -> None:
        state = {"cap": self._cap, "disabled": sorted(self._disabled)}
        staging = self._state_file.with_name(self._state_file.name + ".tmp")
        try:
            staging.write_text(json.dumps(state, indent=2))
            staging.replace(self._state_file)  # Atomic, so a crash never leaves a half-written file
        except OSError as e:
            # The change still applies for this session; only the restart would lose it
            print(f"Could not save tank state to {self._state_file}: {e}")

    def _disable_over_cap(self) -> None:
        while len(self._enabled) > self._cap:
            self._disabled.add(self._enabled.pop(0))

    def register(self, name: str, scan: np.ndarray) -> None:
        """
        Add a photo that scanned into a fish; it is enabled unless it was saved as disabled.
        Each photo is registered once.
        :param name: Photo file name
        :param scan: RGBA scan, for the thumbnail
        """
        thumbnail = thumbnail_png(scan)
        with self._lock:
            self._names.append(name)
            self._thumbnails[name] = thumbnail
            if name not in self._disabled:
                self._enabled.append(name)
                if len(self._enabled) > self._cap:
                    self._disable_over_cap()
                    self._save()

    def __contains__(self, name: str) -> bool:
        with self._lock:
            return name in self._thumbnails

    def enabled(self) -> list[str]:
        """
        :return: Names of the enabled fish, oldest first
        """
        with self._lock:
            return list(self._enabled)

    def set_enabled(self, name: str, enabled: bool) -> None:
        """
        Enable or disable a registered fish
        :param name: Photo file name
        :param enabled: True to make it the newest enabled fish, False to disable it
        """
        with self._lock:
            if enabled == (name in self._enabled):
                return
            if enabled:
                self._disabled.discard(name)
                self._enabled.append(name)
                self._disable_over_cap()
            else:
                self._enabled.remove(name)
                self._disabled.add(name)
            self._save()

    def set_cap(self, cap: int) -> None:
        """
        Change how many fish may be enabled at once; lowering it disables the oldest
        :param cap: Between MIN_CAP and MAX_CAP
        """
        assert MIN_CAP <= cap <= MAX_CAP, f"cap {cap} outside {MIN_CAP}-{MAX_CAP}"
        with self._lock:
            self._cap = cap
            self._disable_over_cap()
            self._save()

    def thumbnail(self, name: str) -> bytes:
        with self._lock:
            return self._thumbnails[name]

    def snapshot(self) -> dict:
        """
        :return: The cap and every registered fish, newest first, with whether it is enabled
        """
        with self._lock:
            return {
                "cap": self._cap,
                "fish": [{"name": name, "enabled": name in self._enabled} for name in reversed(self._names)],
            }
