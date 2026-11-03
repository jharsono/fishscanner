# Troubleshooting Guide

## Installation

### `uv: command not found`
Install uv: `brew install uv` on macOS, or see https://docs.astral.sh/uv/getting-started/installation/.

### Python version errors
The project needs Python 3.11 or newer. uv will download one if none is installed; otherwise check `uv python list`.

### Starting over
```bash
rm -rf .venv
uv sync
```

## Running

### "Could not create an OpenGL 3.3 window"
Your graphics driver does not offer an OpenGL 3.3 core profile. Update your system or graphics drivers. On Linux, make sure you are running inside a desktop session, not over plain SSH.

### Window opens but shows only the dark clear colour
The images are found relative to the package, so the folder you run from does not matter. Run `uv run pytest tests/test_renderer.py -v` and report the output in an issue.

## Fish not appearing

### The photo never shows up
1. Check it is a `.jpg`, `.jpeg` or `.heic` file (any capitalisation) inside the `photos` folder the startup line names (it is relative to where you ran the app).
2. Wait a couple of seconds: a file is only scanned once it has stopped growing.
3. Check the terminal (a photo that loads prints nothing): `Cannot read photo` means the file is corrupt or incomplete; `Markers in the image are not found` means the corner markers were not detected (see below). A photo that fails three times is skipped until the app restarts.
4. A photo that replaces an existing file with the same name is not rescanned; save it under a new name.

### Markers in the image are not found
1. All four corner markers must be fully visible and unobscured
2. Hold the paper flat; strong curl or glare on a marker breaks detection
3. Use even lighting and avoid shadows across the markers
4. Fill the frame with the page, but keep a little margin around the markers

### The fish is cut off or has background attached
1. Keep the drawing inside the marked area; anything crossing the line between two markers is cropped, and a square around each corner marker is blanked
2. Use a solid outline and fill; the background removal keeps the largest connected shape

## Performance

If animation stutters, close other GPU-heavy applications, and keep the `photos` folder to the fish you want: every photo there is scanned at startup. The app caps at 10 fish on screen and retires the oldest.

## Still having problems?

1. Check the [issues page](https://github.com/jharsono/fishscanner/issues) for similar problems
2. Create a new issue with a description, steps to reproduce, any error messages, and your OS and Python version (`uv run python --version`)
