"""
The tank's server on its own, with no window: scan the photos, keep the roster, and serve the
phone remote and the fish to a browser that draws the tank.
"""

import argparse
import sys
from pathlib import Path
from queue import Queue

from engine.photos import PhotoWatcher, list_photos, scan_photo_file
from engine.simplescanner import SimpleScanner
from ocean.roster import FishRoster
from remote.server import RemoteServer, create_app, lan_address

PHOTOS_DIR = Path("photos")
STATE_FILE = PHOTOS_DIR / "tank.json"  # The fish cap and the disabled photos, kept across restarts
SERVER_PORT = 8080  # Remote control page, opened from a phone on the same network
FISH_LIMIT = 10  # Default cap on fish in the tank; the remote control can change it


def load_fish_from_files(scanner: SimpleScanner, scanned_fish_queue: Queue) -> int:
    """
    Scan every photo already in the photos folder
    :param scanner: Object of scanner to process photos
    :param scanned_fish_queue: Queue of (path, RGBA scan) for the main thread, which registers them
    :return: Number of fish found
    """
    found = 0
    for path in list_photos(PHOTOS_DIR):
        scanned_fish = scan_photo_file(path, scanner)
        if scanned_fish is not None:
            scanned_fish_queue.put((path, scanned_fish))
            found += 1
    return found


def main():
    parser = argparse.ArgumentParser(description="Scan fish photos and serve them to the tank and the phone remote")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"TCP port to listen on (default {SERVER_PORT})")
    port = parser.parse_args().port

    scanner = SimpleScanner()
    scanned_fish_queue: Queue = Queue()
    PHOTOS_DIR.mkdir(exist_ok=True)
    roster = FishRoster(STATE_FILE, default_cap=FISH_LIMIT)
    found = load_fish_from_files(scanner, scanned_fish_queue)
    print(f"Loaded {found} fish from {PHOTOS_DIR.resolve()}; drop photos there to add more")

    # Scan photos added while the server runs. A photo that lands between the startup
    # scan above and this start() is treated as already present and will not be scanned.
    watcher = PhotoWatcher(PHOTOS_DIR, scanner, scanned_fish_queue)
    watcher.start()

    # Uploads land in PHOTOS_DIR, where the watcher picks them up like any other new photo
    server = RemoteServer(create_app(roster, PHOTOS_DIR), port=port)
    try:
        server.start()
    except OSError as e:  # The port is taken: without it there is nothing to serve
        watcher.stop()
        sys.exit(f"Cannot listen on port {port}: {e}")
    print(f"Remote control: http://{lan_address()}:{port}")
    print(f"Tank, for a TV's browser: http://{lan_address()}:{port}/tank/")

    try:
        while True:  # The main thread registers scans, as the window's animation loop does
            path, scanned_fish = scanned_fish_queue.get()
            roster.register(path.name, scanned_fish)
    except KeyboardInterrupt:  # Ctrl-C is how the server is stopped
        pass
    finally:
        server.stop()
        watcher.stop()


if __name__ == "__main__":
    main()
