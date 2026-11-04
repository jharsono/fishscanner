"""Tests for the roster of fish in the tank: enabling, the cap, persistence and thumbnails."""

import json
import os
from pathlib import Path

import cv2
import numpy as np
import pytest

from ocean.roster import MAX_CAP, MIN_CAP, FishRoster


def blank_scan() -> np.ndarray:
    return np.zeros((600, 800, 4), dtype=np.uint8)


def decode_png(data: bytes) -> np.ndarray:
    image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_UNCHANGED)
    assert image is not None, "not a decodable image"
    return image


def roster_with(state_file: Path, names: list[str], cap: int = 10) -> FishRoster:
    roster = FishRoster(state_file, default_cap=cap)
    for name in names:
        roster.register(name, blank_scan())
    return roster


def test_new_photos_are_enabled_oldest_first(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg"])
    assert roster.enabled() == ["a.jpg", "b.jpg"]
    assert "a.jpg" in roster and "c.jpg" not in roster


def test_registering_past_the_cap_disables_the_oldest(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg", "c.jpg"], cap=2)
    assert roster.enabled() == ["b.jpg", "c.jpg"]
    assert json.loads((tmp_path / "tank.json").read_text())["disabled"] == ["a.jpg"]


def test_disabled_fish_stay_disabled_after_a_restart(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg"])
    roster.set_enabled("a.jpg", False)
    assert roster.enabled() == ["b.jpg"]
    restarted = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg"])
    assert restarted.enabled() == ["b.jpg"]


def test_enabling_makes_a_fish_the_newest_and_disables_the_oldest_over_the_cap(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg", "c.jpg"], cap=2)
    roster.set_enabled("a.jpg", True)
    assert roster.enabled() == ["c.jpg", "a.jpg"]
    assert json.loads((tmp_path / "tank.json").read_text())["disabled"] == ["b.jpg"]


def test_enabling_an_enabled_fish_changes_nothing(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg"])
    roster.set_enabled("a.jpg", True)
    assert roster.enabled() == ["a.jpg", "b.jpg"]


def test_lowering_the_cap_disables_the_oldest_and_raising_it_enables_nothing(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg", "c.jpg"])
    roster.set_cap(1)
    assert roster.enabled() == ["c.jpg"]
    roster.set_cap(5)
    assert roster.enabled() == ["c.jpg"]
    assert roster.snapshot()["cap"] == 5


def test_the_cap_survives_a_restart(tmp_path: Path):
    roster_with(tmp_path / "tank.json", []).set_cap(4)
    assert FishRoster(tmp_path / "tank.json", default_cap=10).snapshot()["cap"] == 4


def test_a_saved_cap_outside_the_range_is_clamped(tmp_path: Path):
    (tmp_path / "tank.json").write_text(json.dumps({"cap": MAX_CAP + 5, "disabled": []}))
    assert FishRoster(tmp_path / "tank.json", default_cap=10).snapshot()["cap"] == MAX_CAP
    (tmp_path / "tank.json").write_text(json.dumps({"cap": MIN_CAP - 5, "disabled": []}))
    assert FishRoster(tmp_path / "tank.json", default_cap=10).snapshot()["cap"] == MIN_CAP


def test_a_missing_state_file_starts_with_the_default_cap_quietly(tmp_path: Path, capsys):
    roster = FishRoster(tmp_path / "tank.json", default_cap=7)
    assert roster.snapshot() == {"cap": 7, "fish": []}
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("content", ["{not json", "[1, 2]", '{"cap": "many", "disabled": []}', '{"cap": 3}'])
def test_an_unreadable_state_file_starts_from_defaults_with_a_warning(tmp_path: Path, capsys, content: str):
    (tmp_path / "tank.json").write_text(content)
    roster = roster_with(tmp_path / "tank.json", ["a.jpg"], cap=6)
    assert roster.snapshot()["cap"] == 6
    assert roster.enabled() == ["a.jpg"]
    assert "Ignoring unreadable tank state" in capsys.readouterr().out


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores directory permissions")
def test_an_unwritable_state_file_warns_and_keeps_the_change_for_the_session(tmp_path: Path, capsys):
    folder = tmp_path / "photos"
    folder.mkdir()
    roster = roster_with(folder / "tank.json", ["a.jpg", "b.jpg"])
    folder.chmod(0o500)
    try:
        roster.set_enabled("a.jpg", False)
    finally:
        folder.chmod(0o700)
    assert roster.enabled() == ["b.jpg"]
    assert "Could not save tank state" in capsys.readouterr().out


def test_the_snapshot_lists_the_newest_fish_first(tmp_path: Path):
    roster = roster_with(tmp_path / "tank.json", ["a.jpg", "b.jpg", "c.jpg"], cap=2)
    assert roster.snapshot() == {
        "cap": 2,
        "fish": [
            {"name": "c.jpg", "enabled": True},
            {"name": "b.jpg", "enabled": True},
            {"name": "a.jpg", "enabled": False},
        ],
    }


def test_the_thumbnail_is_a_png_of_the_painted_area(tmp_path: Path):
    scan = blank_scan()
    scan[100:200, 300:500] = (255, 0, 0, 255)  # A red patch twice as wide as it is tall
    roster = FishRoster(tmp_path / "tank.json", default_cap=10)
    roster.register("a.jpg", scan)
    data = roster.thumbnail("a.jpg")
    assert data.startswith(b"\x89PNG")
    image = decode_png(data)
    assert image.shape[2] == 4
    assert image.shape[1] == 2 * image.shape[0]  # Cropped to the paint, not the whole page
    assert tuple(int(v) for v in image[image.shape[0] // 2, image.shape[1] // 2]) == (0, 0, 255, 255)  # BGRA red


def test_the_thumbnail_of_an_empty_scan_is_the_whole_page(tmp_path: Path):
    roster = FishRoster(tmp_path / "tank.json", default_cap=10)
    roster.register("a.jpg", blank_scan())
    image = decode_png(roster.thumbnail("a.jpg"))
    assert image.shape[1] * 3 == image.shape[0] * 4
