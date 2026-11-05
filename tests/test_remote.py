"""Tests for the remote control web app, against the real roster, scanner and example photos."""

import json
import socket
import time
import urllib.request
from pathlib import Path
from queue import Queue

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from engine.photos import PhotoWatcher
from engine.simplescanner import SimpleScanner
from ocean import IMAGES_DIR
from ocean.roster import MAX_CAP, MIN_CAP, FishRoster
from remote.server import RemoteServer, create_app, lan_address
from tests.scanner_fixtures import EXAMPLES, PHOTOS

EXAMPLE = PHOTOS / EXAMPLES[0]


@pytest.fixture
def photos(tmp_path: Path) -> Path:
    folder = tmp_path / "photos"
    folder.mkdir()
    return folder


@pytest.fixture
def roster(photos: Path) -> FishRoster:
    roster = FishRoster(photos / "tank.json", default_cap=10)
    scan = np.zeros((600, 800, 4), dtype=np.uint8)
    scan[100:200, 100:300] = 255
    for name in ["a.jpg", "b.jpg"]:
        roster.register(name, scan)
    return roster


@pytest.fixture
def client(roster: FishRoster, photos: Path) -> TestClient:
    return TestClient(create_app(roster, photos))


def photos_in(folder: Path) -> list[str]:
    return sorted(path.name for path in folder.iterdir() if path.name != "tank.json")


def upload(client: TestClient, path: Path, filename: str = "image.jpg", content_type: str = "image/jpeg"):
    with path.open("rb") as f:
        return client.post("/api/photos", files={"photo": (filename, f, content_type)})


def test_the_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "<title>FishScanner</title>" in response.text


def test_the_fish_list_is_newest_first_with_painted_extents_the_cap_and_its_range(client):
    extent = [0.75, pytest.approx(2 / 3)]  # The fixture paints columns 100-299 of 800 and rows 100-199 of 600
    assert client.get("/api/fish").json() == {
        "cap": 10,
        "min_cap": MIN_CAP,
        "max_cap": MAX_CAP,
        "fish": [
            {"name": "b.jpg", "enabled": True, "extent": extent},
            {"name": "a.jpg", "enabled": True, "extent": extent},
        ],
    }


def test_disabling_and_enabling_a_fish(client, roster):
    response = client.put("/api/fish/a.jpg", json={"enabled": False})
    assert response.status_code == 200
    fish = response.json()["fish"][1]
    assert fish["name"] == "a.jpg" and fish["enabled"] is False
    assert roster.enabled() == ["b.jpg"]
    assert client.put("/api/fish/a.jpg", json={"enabled": True}).status_code == 200
    assert roster.enabled() == ["b.jpg", "a.jpg"]


def test_an_unknown_fish_is_not_found(client):
    assert client.put("/api/fish/nope.jpg", json={"enabled": False}).status_code == 404
    assert client.get("/api/fish/nope.jpg/thumbnail").status_code == 404
    assert client.get("/api/fish/nope.jpg/image").status_code == 404


def test_changing_the_cap(client, roster):
    response = client.put("/api/settings", json={"cap": 1})
    assert response.status_code == 200
    assert response.json()["cap"] == 1
    assert roster.enabled() == ["b.jpg"]


@pytest.mark.parametrize("cap", [MIN_CAP - 1, MAX_CAP + 1])
def test_a_cap_outside_the_range_is_rejected(client, roster, cap: int):
    assert client.put("/api/settings", json={"cap": cap}).status_code == 422
    assert roster.snapshot()["cap"] == 10


def test_a_thumbnail_is_a_png(client):
    response = client.get("/api/fish/a.jpg/thumbnail")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")


def test_a_fish_image_is_the_rosters_webp(client, roster):
    response = client.get("/api/fish/a.jpg/image")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["cache-control"] == "max-age=86400"  # A photo is registered once, so it never changes
    assert response.content == roster.image("a.jpg")


@pytest.mark.parametrize("name", ["bubble.png", "scene2.jpg", "scene3.webp"])
def test_the_scene_images_are_served(client, name: str):
    response = client.get(f"/images/{name}")
    assert response.status_code == 200
    assert response.content == (IMAGES_DIR / name).read_bytes()


def test_an_uploaded_photo_is_saved_whole_under_a_new_name(client, photos):
    response = upload(client, EXAMPLE)
    assert response.status_code == 201
    name = response.json()["name"]
    assert name.endswith(".jpg") and name != "image.jpg"
    assert photos_in(photos) == [name]  # No staging file left behind
    assert (photos / name).read_bytes() == EXAMPLE.read_bytes()


def test_uploads_with_the_same_file_name_are_all_kept(client, photos):
    for _ in range(2):
        assert upload(client, EXAMPLE).status_code == 201
    assert len(photos_in(photos)) == 2


def test_an_upload_without_markers_is_rejected_and_not_saved(client, photos, tmp_path: Path, capsys):
    blank = tmp_path / "blank.jpg"
    cv2.imwrite(str(blank), np.full((600, 800, 3), 255, dtype=np.uint8))
    response = upload(client, blank)
    assert response.status_code == 422
    assert "markers" in response.json()["detail"]
    assert photos_in(photos) == []
    assert "Markers in the image are not found" in capsys.readouterr().out


def test_an_upload_that_is_not_a_jpeg_or_heic_is_rejected(client, photos, tmp_path: Path):
    png = tmp_path / "fish.png"
    cv2.imwrite(str(png), np.full((60, 80, 3), 255, dtype=np.uint8))
    response = upload(client, png, filename="fish.png", content_type="image/png")
    assert response.status_code == 415
    assert photos_in(photos) == []


def test_an_uploaded_photo_reaches_the_watcher_exactly_once(client, photos):
    queue: Queue = Queue()
    watcher = PhotoWatcher(photos, SimpleScanner(), queue, poll_interval=0.1, settle_time=0.3)
    watcher.start()
    try:
        name = upload(client, EXAMPLE).json()["name"]
        deadline = time.monotonic() + 5
        while queue.empty() and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(0.5)  # Give a staging file time to be scanned too, if the watcher could see it
    finally:
        watcher.stop()
    assert queue.qsize() == 1
    path, scan = queue.get()
    assert path == photos / name
    assert scan.shape == (600, 800, 4)


def get_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=5) as response:
        return json.load(response)


def test_the_server_listens_on_every_interface_and_answers_until_stopped(roster, photos):
    # Over loopback: the macOS application firewall may block a LAN connection to an unlisted
    # Python even from this machine, so listening on every interface is what is checked here
    server = RemoteServer(create_app(roster, photos), port=0)
    server.start()
    try:
        host, port = server.address
        assert host == "0.0.0.0"
        assert get_json(f"http://127.0.0.1:{port}/api/fish")["cap"] == 10
    finally:
        server.stop()
    with pytest.raises(OSError):  # urllib's URLError is an OSError: connection refused
        get_json(f"http://127.0.0.1:{port}/api/fish")


def test_the_lan_address_belongs_to_this_machine():
    with socket.create_server((lan_address(), 0)):
        pass  # Binding fails for an address that is not one of this machine's


def test_starting_on_a_port_in_use_raises(roster, photos):
    with socket.create_server(("0.0.0.0", 0)) as taken:
        server = RemoteServer(create_app(roster, photos), port=taken.getsockname()[1])
        with pytest.raises(OSError):
            server.start()
        server.stop()  # Harmless when it never started
