"""
Remote control for the tank: a small web app that a phone on the same network opens to upload
photos, enable and disable fish, and set how many may swim at once. It also serves each fish's
image and the scene images, for a browser that draws the tank.
"""

from __future__ import annotations

import secrets
import shutil
import socket
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from engine.photos import PHOTO_SUFFIXES, scan_photo_file
from engine.simplescanner import SimpleScanner
from ocean import IMAGES_DIR
from ocean.roster import MAX_CAP, MIN_CAP, FishRoster

PAGE = Path(__file__).with_name("index.html")
TANK_DIR = Path(__file__).with_name("tank")  # The page that draws the tank, for a TV's browser


class FishUpdate(BaseModel):
    enabled: bool


class Settings(BaseModel):
    cap: int = Field(ge=MIN_CAP, le=MAX_CAP)


def create_app(roster: FishRoster, photos_dir: Path) -> FastAPI:
    """
    :param roster: The fish the page lists and toggles
    :param photos_dir: Folder uploads are saved to; the photo watcher picks them up from there
    :return: The web app
    """
    app = FastAPI(title="FishScanner remote")

    def state() -> dict:
        return {**roster.snapshot(), "min_cap": MIN_CAP, "max_cap": MAX_CAP}

    def require(name: str) -> None:
        if name not in roster:
            raise HTTPException(404, f"No fish from a photo named {name}")

    @app.get("/")
    def page() -> FileResponse:
        return FileResponse(PAGE)

    @app.get("/api/fish")
    def list_fish() -> dict:
        return state()

    @app.get("/api/fish/{name}/thumbnail")
    def thumbnail(name: str) -> Response:
        require(name)
        # A photo is registered once, so its thumbnail never changes
        return Response(roster.thumbnail(name), media_type="image/png", headers={"Cache-Control": "max-age=86400"})

    @app.get("/api/fish/{name}/image")
    def image(name: str) -> Response:
        require(name)
        # A photo is registered once, so its image never changes either
        return Response(roster.image(name), media_type="image/webp", headers={"Cache-Control": "max-age=86400"})

    @app.put("/api/fish/{name}")
    def update_fish(name: str, update: FishUpdate) -> dict:
        require(name)
        roster.set_enabled(name, update.enabled)
        return state()

    @app.put("/api/settings")
    def update_settings(settings: Settings) -> dict:
        roster.set_cap(settings.cap)
        return state()

    @app.post("/api/photos", status_code=201)
    def upload(photo: UploadFile) -> dict:
        suffix = Path(photo.filename or "").suffix.lower()
        if suffix not in PHOTO_SUFFIXES:
            raise HTTPException(415, "Only JPEG and HEIC photos can be scanned")
        # Phones name every upload alike (Safari sends image.jpg), so the name is made here
        name = f"upload-{time.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(2)}{suffix}"
        # Staged under a suffix the watcher ignores, and renamed into place only once it has
        # scanned, so the watcher never sees a partial file or a photo without a fish in it
        staging = photos_dir / f"{name}.upload"
        try:
            with staging.open("wb") as f:
                shutil.copyfileobj(photo.file, f)
            # A scanner per upload: requests run on a thread pool and OpenCV's detector is not shared
            if scan_photo_file(staging, SimpleScanner()) is None:
                raise HTTPException(422, "No drawing found: make sure all four corner markers are in the photo")
            staging.rename(photos_dir / name)
        except OSError as e:  # Disk full, or the photos folder was removed
            raise HTTPException(500, f"Could not save the photo: {e}") from e
        finally:
            staging.unlink(missing_ok=True)
        return {"name": name}

    app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")
    app.mount("/tank", StaticFiles(directory=TANK_DIR, html=True), name="tank")
    return app


class RemoteServer:
    """
    Serve the web app on a background thread; the main thread belongs to the window.
    """

    def __init__(self, app: FastAPI, port: int, host: str = "0.0.0.0"):
        """
        :param app: Web app to serve
        :param port: TCP port, or 0 for any free one
        :param host: Interface to listen on; the default is every interface, so phones on the network can connect
        """
        self._requested = (host, port)
        # Warnings and errors only, through Python's default logging, so the terminal stays quiet
        self._server = uvicorn.Server(uvicorn.Config(app, log_level="warning", log_config=None))
        self._listener: socket.socket | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """
        Listen on the port and start serving
        :raises OSError: When the port cannot be bound, typically because another program is using it
        """
        # Bound here rather than by uvicorn, which would exit its thread on failure where the
        # caller cannot see it; once bound, connections queue until the server accepts them
        self._listener = socket.create_server(self._requested)
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [self._listener]}, daemon=True)
        self._thread.start()

    @property
    def address(self) -> tuple[str, int]:
        """
        :return: Host and port the server listens on, once started
        """
        assert self._listener is not None, "the server has not been started"
        return self._listener.getsockname()[:2]

    def stop(self) -> None:
        self._server.should_exit = True
        if self._thread is not None:
            self._thread.join()


def lan_address() -> str:
    """
    This machine's address on the local network, for a phone on the same Wi-Fi to open
    :return: IPv4 address of the interface that routes outward, or the host name when there is no route
    """
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("192.0.2.1", 9))  # A documentation address: connecting UDP only picks the interface
        except OSError:  # No network route at all
            return socket.gethostname()
        return probe.getsockname()[0]
