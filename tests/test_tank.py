"""The tank page and its JavaScript, run in headless Chrome against the real web app: the tests in
tests/tank/, one page per file, and the page itself drawing the example photos' fish.

Skipped where Google Chrome is not installed.
"""

import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.staticfiles import StaticFiles
from playwright.sync_api import Browser, Page, sync_playwright
from playwright.sync_api import Error as PlaywrightError

from engine.simplescanner import SimpleScanner
from ocean.roster import FishRoster
from remote.server import RemoteServer, create_app
from tests.scanner_fixtures import EXAMPLES, PHOTOS, REPO, scan_photo

JS_TESTS = REPO / "tests" / "tank"
# Software WebGL: the same pixels on any machine, and a WebGL even on a CI runner with no GPU
CHROME_ARGS = ["--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
# ANGLE reports reading pixels back as a performance stall, a few times per context and then once
# more saying it will stop; the GL tests read pixels on purpose
READ_PIXELS_NOTICE = re.compile(
    r"\[\.WebGL-0x[0-9a-f]+\]GL Driver Message \(OpenGL, Performance, GL_CLOSE_PATH_NV, High\): "
    r"GPU stall due to ReadPixels( \(this message will no longer repeat\))?"
)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(channel="chrome", args=CHROME_ARGS)
        except PlaywrightError as e:  # Google Chrome is not installed on this machine
            pytest.skip(f"Google Chrome is not available: {e.message.splitlines()[0]}")
        yield browser
        browser.close()


def serve(app) -> RemoteServer:
    server = RemoteServer(app, port=0, host="127.0.0.1")
    server.start()
    return server


@pytest.fixture(scope="module")
def site(tmp_path_factory: pytest.TempPathFactory):
    """The web app over loopback, serving the tank at its own paths and the tests beside it"""
    photos: Path = tmp_path_factory.mktemp("photos")
    app = create_app(FishRoster(photos / "tank.json", default_cap=10), photos)
    app.mount("/tests/tank", StaticFiles(directory=JS_TESTS), name="tests")
    server = serve(app)
    yield f"http://127.0.0.1:{server.address[1]}"
    server.stop()


@pytest.fixture(scope="module")
def tank(tmp_path_factory: pytest.TempPathFactory):
    """The web app with the example photos registered, as the server has them once it has scanned them"""
    photos: Path = tmp_path_factory.mktemp("tank")
    roster = FishRoster(photos / "tank.json", default_cap=10)
    scanner = SimpleScanner()
    for name in EXAMPLES:
        roster.register(name, scan_photo(scanner, PHOTOS / name))
    server = serve(create_app(roster, photos))
    yield f"http://127.0.0.1:{server.address[1]}", roster
    server.stop()


def watch(page: Page) -> list[str]:
    """Collect everything the page logs or throws"""
    messages: list[str] = []
    page.on("console", lambda message: messages.append(message.text))
    page.on("pageerror", lambda error: messages.append(str(error)))
    return messages


def unexpected_messages(messages: list[str]) -> list[str]:
    return [message for message in messages if not READ_PIXELS_NOTICE.fullmatch(message)]


@pytest.mark.parametrize("file", sorted(path.name for path in JS_TESTS.glob("*.test.js")))
def test_tank_javascript(browser: Browser, site: str, file: str):
    page = browser.new_page()
    messages = watch(page)
    try:
        page.goto(f"{site}/tests/tank/runner.html")
        results = page.evaluate("file => window.runTests(file)", file)
    finally:
        page.close()
    assert results, f"{file} registered no tests"
    failures = [f"{result['name']}:\n{result['error']}" for result in results if result["error"]]
    assert not failures, "\n\n".join(failures)
    assert not unexpected_messages(messages)


def test_the_tank_page_swims_the_enabled_fish_and_follows_the_roster(browser: Browser, tank):
    url, roster = tank
    page = browser.new_page(viewport={"width": 960, "height": 540})
    messages = watch(page)
    try:
        page.goto(f"{url}/tank/")
        page.wait_for_function("window.tank.scene.swimming.size === 2")
        assert page.evaluate("[window.tank.canvas.width, window.tank.canvas.height]") == [960, 540]
        roster.set_enabled(EXAMPLES[0], False)  # As the phone remote does
        page.wait_for_function("window.tank.scene.swimming.size === 1")
        assert page.evaluate("[...window.tank.scene.swimming.keys()]") == [EXAMPLES[1]]
        # The scene is drawn: the backgrounds cover the canvas rather than leaving the clear colour
        page.wait_for_load_state("networkidle")  # Every image has arrived
        shot = cv2.imdecode(np.frombuffer(page.screenshot(), np.uint8), cv2.IMREAD_COLOR)
        assert shot is not None, "the screenshot is not decodable"
        clear = (shot == np.array([51, 26, 26], dtype=np.uint8)).all(axis=2)  # BGR of the clear colour
        assert clear.mean() < 0.05, f"{clear.mean():.0%} of the canvas is still the clear colour"
    finally:
        page.close()
    assert not unexpected_messages(messages)
