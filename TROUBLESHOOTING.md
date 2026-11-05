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

### The tank page says "This browser cannot draw the tank: it has no WebGL"
The browser does not offer WebGL, or has it turned off. Try another browser on that device, or update its software.

### The tank page shows only a dark blue screen
The page could not load the scene's images from the server. Check that the server is still running, then reload the page. The images are found relative to the package, so the folder you run the server from does not matter.

### The tank stops changing when fish are added or disabled
The page asks the server for changes every couple of seconds. If the server stops, the fish keep swimming as they were, and the page picks changes up again once the server is back.

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

## Phone remote and TV

### The phone or TV cannot open the page
1. The phone or TV must be on the same Wi-Fi as the computer, and use the address from the `Remote control:` or `Tank` line exactly, port included.
2. On macOS the firewall (System Settings > Network > Firewall) blocks incoming connections to an app until you allow it. If you missed or declined the prompt, allow the Python that uv installed; `uv run python -c "import os, sys; print(os.path.realpath(sys.executable))"` prints its path. Either add it under Firewall > Options, or run:
   ```bash
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add <that path>
   sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp <that path>
   ```
   The path changes when uv installs a new Python version, so this may need repeating then.
3. Some guest and venue networks stop devices from reaching each other; use a phone hotspot or a home network instead.

### `Cannot listen on port 8080`
Another program is using the port, and the server stops. Quit the other program, or start the server on another port with `uv run fishscanner --port 8000` and use the addresses it prints.

## Performance

If the tank stutters on a TV, set fewer fish from the phone remote: the TV draws every fish and the full-screen scene each frame. Keep the `photos` folder to the fish you want, too: every photo there is scanned at startup. The app caps the number of fish swimming at once (10 to start, changeable from the phone remote) and disables the oldest beyond it.

## Still having problems?

1. Check the [issues page](https://github.com/jharsono/fishscanner/issues) for similar problems
2. Create a new issue with a description, steps to reproduce, any error messages, and your OS and Python version (`uv run python --version`)
