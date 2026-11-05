# FishScanner

A magical application that brings your fish drawings to life in a virtual ocean! Draw a fish on paper, photograph it, and watch it swim around with other fish in a beautiful underwater world.

This project is based on the wonderful work by [David Svitov](https://github.com/david-svitov/fishscanner), who created the original FishScanner. This version extends his creative vision with HEIC support (iPhone photos), live updates so you can add new fish without restarting, fish that swim into the distance and back, a tank that any web browser can show (a TV's included), a phone remote, and a tested, modern Python stack.

> Forked from [david-svitov/fishscanner](https://github.com/david-svitov/fishscanner)

![Run example](./images/img1.png)

Inspired by this [video](https://www.youtube.com/watch?v=ILrr8vToR9Y&feature=emb_logo) from Workinman Interactive LLC.

## Installation

You need Python 3.11 or newer and [uv](https://docs.astral.sh/uv/). On macOS: `brew install uv`.

```bash
git clone https://github.com/jharsono/fishscanner.git
cd fishscanner
uv sync
```

That's it. No graphics packages, and the machine that runs it needs no screen: a Raspberry Pi will do.

## How to Use

1. Print a template
   - Choose any template from `ocean/patterns/fish_1.pdf` through `fish_5.pdf`, or `blank.pdf` to draw your own shape
   - Each template has special markers in the corners for detection
   ![Scan example](./images/img2.jpg)

2. Draw your fish
   - Use any colors or designs you like
   - Keep your drawing inside the marked area
   - Make sure the corner markers stay visible

3. Run the server

   ```bash
   uv run fishscanner  # add --port 8000 if 8080 is taken
   ```

   It prints two addresses, like `Remote control: http://192.168.1.23:8080` and `Tank, for a TV's browser: http://192.168.1.23:8080/tank/`. Stop it with Ctrl-C.

4. Show the tank: open the tank's address in a web browser on the same network, such as a smart TV's or a streaming stick's (the Fire TV's Silk browser, a Samsung TV's Internet app), or a computer's. The browser needs WebGL; the page is written for browsers as old as a 2022 Samsung TV's (Chromium 85).

5. Add your fish
   - Take a photo of your drawing and save it to the `photos` folder in the directory you run the command from (the repository's own `photos/` if you followed the steps above; it is created if missing), or send it from the phone remote (below)
   - Supported formats: JPG/JPEG and HEIC (iPhone photos)
   - The fish appears in the tank a couple of seconds after the file finishes copying; no restart needed. The terminal prints which folder it is watching at startup and otherwise stays quiet unless something went wrong
   - Photos already in the folder are loaded at startup

## Phone remote

Open the `Remote control:` address on a phone on the same Wi-Fi to:

- **Add a fish**: take or pick a photo of a drawing. It is scanned straight away, so a photo without all four markers is turned down with a message instead of being saved; a good one is saved into `photos/` and swims in a couple of seconds later.
- **Enable or disable fish**: a disabled fish swims off screen and an enabled one swims back in. The photo stays in `photos/` either way, and the choice is remembered across restarts (in `photos/tank.json`).
- **Set how many fish swim at once** (1-30, 10 to start). Going over it, by adding or enabling a fish or by lowering the number, disables the oldest fish.

There is no password: anyone on the same network who finds the address can use it, so use it on a network you trust. On macOS, allow incoming connections when asked the first time (see [Troubleshooting](TROUBLESHOOTING.md#the-phone-or-tv-cannot-open-the-page) if the phone or TV cannot connect).

## Controls

On the tank page:

- **Click** (select on a TV remote) or **F**: fullscreen
- **Left / Right arrows**: switch between ocean scenes
- The tank fits any window or screen

## How it works

- Photos are scanned with OpenCV: the four ArUco markers locate the page, the drawing is warped flat and its background removed.
- A background thread watches `photos/` and only scans a file once it has stopped growing, so a photo still being copied is never read half-written.
- The tank page draws the aquarium with WebGL. It asks the server every couple of seconds which fish are enabled and fetches each new fish's image. Fish swim, turn at the edges, blow bubbles, and drift into the distance and back. Each screen showing the tank swims its own fish, so two screens show the same fish but not in the same places.

## Platform notes

Developed and tested on macOS (Apple Silicon). Every dependency ships as a wheel for Windows and Linux too, so the server should run there as well, a Raspberry Pi with no screen included.

- **Linux**: OpenCV needs `libgl1` and `libglib2.0-0` (`sudo apt-get install libgl1 libglib2.0-0`).

## Troubleshooting

See the [Troubleshooting Guide](TROUBLESHOOTING.md).

## Development

```bash
uv run pytest              # tests, including the tank page in headless Chrome
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pyright             # type check
```

The same checks run in GitHub Actions on Ubuntu (Python 3.11 and 3.14). The tank page's JavaScript tests (`tests/tank/`) run in the installed Google Chrome through Playwright, and skip where Chrome is not installed.

## Project Structure

- `ocean/patterns/`: Fish templates for printing
- `photos/`: Place your fish photos here (only the two examples are tracked in git)
- `engine/`: Scanner and photo ingestion
- `ocean/`: The fish roster, and the tank's image assets
- `main_server.py`: The app: scanning, the fish roster and the web server
- `remote/`: The web app: the phone remote page and its API, and in `remote/tank/` the tank page (plain JavaScript and WebGL, no build step)

The earlier desktop app, which drew the tank in its own window, is kept at the `desktop-final` tag, and its Raspberry Pi build at `desktop-pi`.
