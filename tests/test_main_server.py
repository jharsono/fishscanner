"""The standalone server, run as a process the way it is deployed: real photos, real HTTP, Ctrl-C to stop."""

import json
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

from engine.simplescanner import SimpleScanner
from ocean import IMAGES_DIR
from remote.server import lan_address
from tests.scanner_fixtures import EXAMPLES, PHOTOS, REPO, scan_photo

SCRIPT = REPO / "main_server.py"


def free_port() -> int:
    with socket.create_server(("0.0.0.0", 0)) as probe:
        return probe.getsockname()[1]


def start_server(folder: Path, port: int) -> subprocess.Popen:
    """Run the server from folder, so its photos/ is folder/photos"""
    command = [sys.executable, str(SCRIPT), "--port", str(port)]
    return subprocess.Popen(command, cwd=folder, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def get(port: int, path: str) -> bytes:
    # Over loopback: the macOS application firewall may block a LAN connection to an unlisted Python
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=5) as response:
        return response.read()


def wait_for_fish(server: subprocess.Popen, port: int, count: int, timeout: float = 30) -> list[dict]:
    deadline = time.monotonic() + timeout
    while True:
        assert server.poll() is None, f"the server exited: {server.communicate()[1]}"
        try:
            fish = json.loads(get(port, "/api/fish"))["fish"]
        except OSError:  # Not listening yet: the startup scan comes first
            fish = []
        if len(fish) >= count:
            return fish
        assert time.monotonic() < deadline, f"{len(fish)} fish after {timeout} s, expected {count}"
        time.sleep(0.1)


def test_the_server_scans_photos_present_and_added_serves_them_and_stops_on_ctrl_c(tmp_path: Path):
    photos = tmp_path / "photos"
    photos.mkdir()
    shutil.copy(PHOTOS / EXAMPLES[0], photos / "first.jpg")
    port = free_port()
    server = start_server(tmp_path, port)
    try:
        assert [fish["name"] for fish in wait_for_fish(server, port, 1)] == ["first.jpg"]
        shutil.copy(PHOTOS / EXAMPLES[1], photos / "second.jpg")  # For the watcher to find
        assert [fish["name"] for fish in wait_for_fish(server, port, 2)] == ["second.jpg", "first.jpg"]
        image = cv2.imdecode(np.frombuffer(get(port, "/api/fish/first.jpg/image"), np.uint8), cv2.IMREAD_UNCHANGED)
        assert image is not None, "the fish image is not decodable"
        assert np.array_equal(image[..., 3], scan_photo(SimpleScanner(), PHOTOS / EXAMPLES[0])[..., 3])
        assert get(port, "/images/bubble.png") == (IMAGES_DIR / "bubble.png").read_bytes()
    finally:
        server.send_signal(signal.SIGINT)
        out, err = server.communicate(timeout=10)
    assert server.returncode == 0
    assert err == ""
    assert out.splitlines() == [
        f"Loaded 1 fish from {photos.resolve()}; drop photos there to add more",
        f"Remote control: http://{lan_address()}:{port}",
    ]


def test_the_server_exits_with_a_message_when_its_port_is_taken(tmp_path: Path):
    with socket.create_server(("0.0.0.0", 0)) as taken:
        port = taken.getsockname()[1]
        server = start_server(tmp_path, port)
        out, err = server.communicate(timeout=30)
    assert server.returncode == 1
    assert err.startswith(f"Cannot listen on port {port}: ") and err.count("\n") == 1  # One line, no traceback
    assert out == f"Loaded 0 fish from {(tmp_path / 'photos').resolve()}; drop photos there to add more\n"
