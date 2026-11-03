# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FishScanner (fork of david-svitov/fishscanner): a desktop Python/OpenGL app that turns photos of hand-drawn fish into animated sprites in a virtual aquarium. Photos dropped into `photos/` are scanned (ArUco markers → perspective warp → background removal) and appear live without restarting.

## Commands

There is no test suite, linter, or build step. The only entry point is `main_ocean.py`.

```bash
./setup.sh                 # macOS only: brew deps (glfw, python@3.11, freeglut, XQuartz), creates ./venv, pip installs
./run.sh                   # validates venv/Python 3.11/OpenGL, starts XQuartz, sets DISPLAY=:0, runs main_ocean.py; logs to fishscanner.log
source venv/bin/activate && python3 main_ocean.py   # direct run (needs DISPLAY and XQuartz running)
```

Both scripts `tee` all output to a log file (`setup.log` / `fishscanner.log`); `*.log` is gitignored. `setup.sh` deletes and recreates `venv/` every time it runs. Python must be exactly 3.11 (`run.sh` refuses otherwise). `requirements.txt` pins numpy <2 and opencv <5.

To try the scanner without the GL window, the commented-out block at the bottom of `engine/simplescanner.py` shows the two-call pipeline (`scan` then `remove_background`) on a BGR→RGB frame; `photos/example_fish1.jpg` and `example_fish2.jpg` are valid inputs. Everything else in `photos/` is gitignored.

## Git discipline

One commit per branch and per PR. Squash follow-up commits into the branch's single commit before handing it over, and never commit directly to main.

## Architecture

Two packages plus one script:

- `engine/` is a tiny generic sprite engine over legacy fixed-function OpenGL (GLUT window, `glPushMatrix`/`glTranslatef`, client-side vertex arrays, GLSL 1.x shaders using `gl_Vertex`/`gl_ModelViewProjectionMatrix`). `main()` requests a 3.3 core profile but the code relies on compatibility-profile features throughout; don't "modernize" one side without the other.
  - `Drawing` (`engine/drawing.py`): base sprite. A unit quad subdivided into a `grid_x × grid_y` triangle mesh (so vertex shaders can bend it), with `position`/`rotate`/`scale`/`color` numpy arrays and two VBOs. `render()` binds the texture and shader and feeds a bouncing `timer` uniform. Subclasses override `animation()` and `get_child_sprites()`.
  - `Renderer` (`engine/renderer.py`): sets GL state, builds an ortho projection from the window aspect, and does a two-pass render each frame: opaque sprites with depth writes, then sprites flagged `is_transparent` with depth writes off, both sorted back-to-front on `position[2]`. `animate()` walks every sprite and its children (bubbles) then posts a redisplay. Also the static texture/shader factories; `create_texture_from_file` expects a 4-channel image.
  - `SimpleScanner` (`engine/simplescanner.py`): detects the four ArUco `DICT_4X4_50` markers (ids 3/1/2/4 = TL/TR/BR/BL, hard-coded to match the PDFs in `ocean/patterns/`), warps the page to a rectangle, then `remove_background` resizes to 800×600, thresholds a red-weighted grayscale, keeps the largest contour as the alpha mask, and masks out 110px corner squares where the markers sit. `scan` raises `ValueError` when markers are missing; callers catch it and skip the photo.
- `ocean/` is the aquarium scene built on the engine: `DrawingFish` (state machine `init` → `swim` → `finish`, spawns `DrawingBubble` children, flips via a y-rotation when it hits a wall, `go_away()` starts the exit animation and `is_alive` flips when off-screen), `DrawingSeaweed`/`DrawingStatic` (behaviour lives in the vertex shaders `FISH_SHADER_CODE` / `SEAWEED_SHADER_CODE` which sine-wave the mesh), and the PNG/JPG/WEBP assets in `ocean/images/`. `ocean/debug.py` defines `DEBUG_MODE` env flags but nothing imports it.
- `main_ocean.py` wires it together and owns all app state:
  - **Scenes**: `background_scenes` list in `main()`; `type: 'complex'` builds the full reef (`draw_complex_ocean`), `type: 'simple'` is a single background image. Left/Right arrows cycle scenes via `update_scene`, which drops every non-fish sprite and rebuilds. ESC exits.
  - **Fish lifecycle**: `load_fish_from_files` scans `photos/*.jpg` and `*.heic` at startup. A `watchdog` observer on a daemon thread (`PhotoHandler.on_created`) scans new files off the GL thread and pushes RGBA arrays onto `scanned_fish_queue`; the GLUT timer callback (`animate`, 60 Hz) drains that queue and creates GL textures there, because GL calls must happen on the main thread. `fish_queue` preserves insertion order so when the count exceeds `fish_limit` (10) the oldest fish is told to `go_away()`.
  - **HEIC**: `pillow_heif.register_heif_opener()` at import time; HEIC goes PIL → RGB → BGR so it enters the same path as `cv2.imread`.
  - **Cleanup**: `cleanup_and_exit` stores GL handles and the observer as attributes on itself (`cleanup_and_exit.fish_shader = ...`) so ESC can delete shaders/textures/VBOs and call `os._exit(0)`. New GL resources created in scene builders must be registered there or they leak.

## Things that are stale or easy to get wrong

- `TROUBLESHOOTING.md` has a "Camera Problems" section mentioning a `camera_id` parameter. There is no camera code; input is only files in `photos/`.
- Coordinate system is inverted on Y: `Renderer` calls `glOrtho(-aspect, aspect, 1, -1, ...)`, so smaller Y is higher on screen (fish `_top = -0.7`, `_bottom = 0.3`).
- `Renderer.render` and `animate` iterate `drawings_list` while `update_scene` and the fish-removal loop mutate it in place (`drawings_list[:] = ...`, `.remove()` during iteration). Keep mutations on the GLUT thread.
