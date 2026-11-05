# FishScanner

A magical application that brings your fish drawings to life in a virtual ocean! Draw a fish on paper, photograph it, and watch it swim around with other fish in a beautiful underwater world.

This project is based on the wonderful work by [David Svitov](https://github.com/david-svitov/fishscanner), who created the original FishScanner. This version extends his creative vision with HEIC support (iPhone photos), live updates so you can add new fish without restarting, fish that swim into the distance and back, a native window that needs no X11, and a tested, modern Python stack.

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

That's it. No X11, no system OpenGL packages, no logging out.

## How to Use

1. Print a template
   - Choose any template from `ocean/patterns/fish_1.pdf` through `fish_5.pdf`, or `blank.pdf` to draw your own shape
   - Each template has special markers in the corners for detection
   ![Scan example](./images/img2.jpg)

2. Draw your fish
   - Use any colors or designs you like
   - Keep your drawing inside the marked area
   - Make sure the corner markers stay visible

3. Run the app

   ```bash
   uv run fishscanner
   ```

4. Add your fish
   - Take a photo of your drawing and save it to the `photos` folder in the directory you run the command from (the repository's own `photos/` if you followed the steps above; it is created if missing)
   - Supported formats: JPG/JPEG and HEIC (iPhone photos)
   - The fish appears in the ocean a couple of seconds after the file finishes copying; no restart needed. The terminal prints which folder it is watching at startup and otherwise stays quiet unless something went wrong
   - Photos already in the folder are loaded at startup

## Phone remote

When the app starts it prints a line like `Remote control: http://192.168.1.23:8080`. Open that address on a phone on the same Wi-Fi to:

- **Add a fish**: take or pick a photo of a drawing. It is scanned straight away, so a photo without all four markers is turned down with a message instead of being saved; a good one is saved into `photos/` and swims in a couple of seconds later.
- **Enable or disable fish**: a disabled fish swims off screen and an enabled one swims back in. The photo stays in `photos/` either way, and the choice is remembered across restarts (in `photos/tank.json`).
- **Set how many fish swim at once** (1-30, 10 to start). Going over it, by adding or enabling a fish or by lowering the number, disables the oldest fish.

There is no password: anyone on the same network who finds the address can use it, so use it on a network you trust. On macOS, allow incoming connections when asked the first time (see [Troubleshooting](TROUBLESHOOTING.md#the-phone-cannot-open-the-remote-control-page) if the phone cannot connect).

## Controls

- **Left / Right arrows**: switch between ocean scenes
- **F**: switch between fullscreen and a window
- **ESC**: exit
- The window can be resized

## How it works

- Photos are scanned with OpenCV: the four ArUco markers locate the page, the drawing is warped flat and its background removed.
- The aquarium is drawn with OpenGL in a glfw window: a 3.3 core profile where the driver offers one, OpenGL ES 2.0 otherwise. Fish swim, turn at the edges, blow bubbles, and drift into the distance and back.
- A background thread watches `photos/` and only scans a file once it has stopped growing, so a photo still being copied is never read half-written.

## Platform notes

Developed and tested on macOS (Apple Silicon) and a Raspberry Pi 3B. Every dependency ships as a wheel for Windows and Linux too, and the app only needs a driver offering OpenGL 3.3 or OpenGL ES 2.0, so it should run there as well.

- **Linux**: OpenCV needs `libgl1` and `libglib2.0-0` (`sudo apt-get install libgl1 libglib2.0-0`).
- **Raspberry Pi 3B**: use the 64-bit Raspberry Pi OS with desktop (tested with the Debian 13 "Trixie" image of 2026-10-06). The 32-bit OS has no prebuilt numpy, OpenCV or Pillow wheels, and building them on the Pi is impractical. The Pi's GPU offers OpenGL ES 2.0, which the app picks automatically, and it holds at most 2048 pixels a side, so the backgrounds are shrunk when they load. In a terminal on the Pi's desktop (not over SSH):

  ```bash
  sudo apt install -y git
  curl -LsSf https://astral.sh/uv/install.sh | sh
  source ~/.local/bin/env    # puts uv on the PATH of this terminal
  git clone https://github.com/jharsono/fishscanner.git && cd fishscanner
  uv sync
  uv run fishscanner
  ```

  Press **F** for fullscreen: it runs nearly twice as fast there as in a maximised window. With 10 fish at 1080p that is about 10 frames per second fullscreen against 6 maximised.

## Troubleshooting

See the [Troubleshooting Guide](TROUBLESHOOTING.md).

## Development

```bash
uv run pytest              # tests, including OpenGL smoke tests in a hidden window
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pyright             # type check
```

The same checks run in GitHub Actions on Ubuntu (Python 3.11 and 3.14); the OpenGL tests skip there and run locally, under OpenGL 3.3 on a Mac and under OpenGL ES 2.0 on a Raspberry Pi 3B.

## Project Structure

- `ocean/patterns/`: Fish templates for printing
- `photos/`: Place your fish photos here (only the two examples are tracked in git)
- `engine/`: Scanner, photo ingestion, renderer, shaders
- `ocean/`: The aquarium scene: fish, bubbles, seaweed and image assets
- `main_ocean.py`: The application: window, scenes, main loop
