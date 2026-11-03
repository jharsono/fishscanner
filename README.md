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
   - The fish appears in the ocean a couple of seconds after the file finishes copying; no restart needed. The terminal stays quiet unless something went wrong
   - Photos already in the folder are loaded at startup

## Controls

- **Left / Right arrows**: switch between ocean scenes
- **ESC**: exit
- The window can be resized

## How it works

- Photos are scanned with OpenCV: the four ArUco markers locate the page, the drawing is warped flat and its background removed.
- The aquarium is drawn with OpenGL 3.3 in a glfw window. Fish swim, turn at the edges, blow bubbles, and drift into the distance and back.
- A background thread watches `photos/` and only scans a file once it has stopped growing, so a photo still being copied is never read half-written.

## Platform notes

Developed and tested on macOS (Apple Silicon). Every dependency ships as a wheel for Windows and Linux too, and the app only needs an OpenGL 3.3 capable driver, so it should run there as well.

- **Linux**: OpenCV needs `libgl1` and `libglib2.0-0` (`sudo apt-get install libgl1 libglib2.0-0`).

## Troubleshooting

See the [Troubleshooting Guide](TROUBLESHOOTING.md).

## Development

```bash
uv run pytest              # tests, including OpenGL smoke tests in a hidden window
uv run ruff check .        # lint
uv run ruff format .       # format
uv run pyright             # type check
```

The same checks run in GitHub Actions on Ubuntu (Python 3.11 and 3.14); the OpenGL tests skip there and run locally on a Mac.

## Project Structure

- `ocean/patterns/`: Fish templates for printing
- `photos/`: Place your fish photos here (only the two examples are tracked in git)
- `engine/`: Scanner, photo ingestion, renderer, shaders
- `ocean/`: The aquarium scene: fish, bubbles, seaweed and image assets
- `main_ocean.py`: The application: window, scenes, main loop
