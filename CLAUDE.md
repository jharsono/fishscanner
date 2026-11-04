# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

FishScanner (fork of david-svitov/fishscanner): a desktop Python/OpenGL app that turns photos of hand-drawn fish into animated sprites in a virtual aquarium. Photos dropped into `photos/` are scanned (ArUco markers → perspective warp → background removal) and appear live without restarting.

## Commands

The only entry point is `main_ocean.py` (console script `fishscanner`).

```bash
uv sync                    # creates .venv from pyproject.toml + uv.lock (Python >= 3.11)
uv run fishscanner         # runs the app (native glfw window, no X11)
uv run pytest              # all tests; GL tests render into a hidden window and skip where none can be created
uv run ruff check . && uv run ruff format --check . && uv run pyright   # the CI gates (Ubuntu only; GL tests run locally)
```

Run everything with `PYTHONDONTWRITEBYTECODE=1` when mutating source during a test session: a same-length edit restored within one second can leave a stale `.pyc` in use.

To try the scanner without the GL window, the commented-out block at the bottom of `engine/simplescanner.py` shows the two-call pipeline (`scan` then `remove_background`) on a BGR→RGB frame; `photos/example_fish1.jpg` and `example_fish2.jpg` are valid inputs. Everything else in `photos/` is gitignored.

## Git discipline

One commit per branch and per PR. Squash follow-up commits into the branch's single commit before handing it over, and never commit directly to main.

## Architecture

Two packages plus one script:

- `engine/` is a tiny generic sprite engine on OpenGL 3.3 core (glfw window, VAOs, GLSL 3.30, no fixed-function calls).
  - `engine/shaders.py`: one vertex header and one fragment shader shared by every sprite program. A sprite kind supplies only a GLSL `vec4 transform(vec3 p)` function (the fish tail beat and seaweed sway live in `ocean/`; `timer` is a slow per-sprite bounce, `params` four per-sprite numbers), and `compile_program()` returns a `ShaderProgram` with cached uniform locations. The fragment shader discards texels with alpha ≤ 0.1, which replaces the old alpha test.
  - `engine/matrices.py`: numpy model/orthographic matrices, tested without GL. Model = translate · rotate x · rotate y · rotate z · scale.
  - `Drawing` (`engine/drawing.py`): base sprite. A unit quad subdivided into a `grid_x × grid_y` triangle mesh (so vertex shaders can bend it); meshes are uploaded once per grid size and shared (`Drawing.release_meshes()` at shutdown). `render(projection, default_shader)` sets `model`, `projection`, `color` and the bouncing `timer` uniform. Subclasses override `animation()` and `get_child_sprites()`.
  - `Renderer` (`engine/renderer.py`): GL state, the ortho projection from the framebuffer aspect, the default program, and a two-pass render each frame: opaque sprites with depth writes, then sprites flagged `is_transparent` with depth writes off and drawn farthest-first so nearer ones paint over (larger z is nearer). `animate()` and `render()` both walk every sprite and its children (bubbles) via `all_sprites()`. Texture factories accept gray/BGR/BGRA files.
  - `SimpleScanner` (`engine/simplescanner.py`): detects the four ArUco `DICT_4X4_50` markers (ids 3/1/2/4 = TL/TR/BR/BL, hard-coded to match the PDFs in `ocean/patterns/`), warps the page to the rectangle of their outer corners, then `remove_background` resizes to 800×600 and builds a mask from ink strokes (adaptive threshold on a red-weighted grayscale of the RGB input) OR painted colour (HSV saturation more than `paint_saturation_margin` above the paper's, measured from the frame's blank border, and value above `paint_min_value`), keeps the largest contour as the alpha mask, and blanks 110px corner squares where the markers sit. Counting paint as drawing is what keeps a filled fin opaque when the crop cuts its outline. `scan` raises `ValueError` when markers are missing; callers catch it and skip the photo.
- `ocean/` is the aquarium scene built on the engine. `DrawingFish` is a state machine `init` → `swim` → `finish`: the entry animation, then swimming with a slow cosine *distance cycle* (`distance_cycle`, random 10-25 s period) that shrinks the fish to `FAR_SCALE`, slows it to `FAR_SPEED`, tints it to `FAR_TINT` and pushes it to `FAR_Z` before growing it back; facing lives in the sign of `_base_scale[0]`, never in the drawn `scale`. At a border it turns only when beyond the edge *and* heading outward (a position-only check made fish that started past a border spin forever). `go_away()` starts the exit and `is_alive` flips when off-screen. Bubbles are `DrawingBubble` children that inherit the fish's distance. `FISH_TRANSFORM` is a side-view tail beat that foreshortens the tail in x and never moves y, driven by the fish's own beat phase and swing in `shader_params` (the `params` uniform), which `animation()` advances from the fish's `tempo` and its current `effort` (rest/cruise/burst, re-chosen every few seconds and eased); speed is vector × distance factor × effort; `SEAWEED_TRANSFORM` sways the mesh with the slow `timer` bounce. Image assets live in `ocean/images/`, print templates in `ocean/patterns/`.
- `main_ocean.py` wires it together: `create_window()` opens the glfw window (3.3 core, forward-compatible, vsync); `main()` runs a fixed-step loop driven by `engine/clock.py`'s `FixedStepClock` (60 Hz `step()` ticks with a carried remainder and a 0.25 s stall cap, render every frame). Resizing calls `Renderer.resize`, which refits the viewport and projection so world units stay square; beyond `max_aspect` (the backgrounds' own 1.8:1) a wider window crops vertically rather than revealing space past the backgrounds.
  - **Scenes**: `Scene` owns the sprite list, the fish/seaweed programs and the background configs; `type: 'complex'` builds the full reef, `type: 'simple'` is one background image from `ocean.IMAGES_DIR` (package-relative, so the console script works from any directory). Left/Right arrows call `switch_background`, which drops every non-fish sprite and rebuilds. ESC closes the window.
  - **Fish lifecycle**: `engine/photos.py` owns photo discovery (`.jpg/.jpeg/.heic`, any case), decoding (both through PIL/pillow-heif with EXIF orientation applied; `None` on truncated or undecodable data, which OpenCV would silently decode partially) and scanning. At startup `load_fish_from_files` scans every photo already present; afterwards a `PhotoWatcher` daemon thread polls the folder and scans a new file only once its size has been stable for a settle time, retrying with backoff if the scan fails (stalled copy, truncated file, markers not found). Both push RGBA arrays onto `scanned_fish_queue`; the 60 Hz `step()` on the main thread drains that queue and creates GL textures there, because GL calls must happen on the main thread. `fish_queue` preserves insertion order so when the count exceeds `fish_limit` (10) the oldest fish is told to `go_away()`.
  - **Cleanup**: decoration textures are cached by file in `Scene` so switching scenes never allocates; every texture and program goes through the `Resources` registry (`resources.texture(...)` / `resources.program(...)`) so `main()` can delete them, release the shared meshes and `glfw.terminate()` on exit. A dead fish's texture is released when it is removed.

## Things that are stale or easy to get wrong

- Coordinate system is inverted on Y: `Renderer.resize` builds `orthographic(-half_width, half_width, half_height, -half_height, -1, 1)`, so smaller Y is higher on screen (fish `_top = -0.7`, `_bottom = 0.3`).
- The sprite list is only ever mutated on the main thread inside `step()` or a key callback; off-screen bubbles and dead fish are culled by rebuilding lists, never by removing during iteration.
- `SimpleScanner.remove_background` receives RGB (see `engine/photos.py`) but unpacks it as `b, g, r = cv2.split(frame)`, so the "red" weight of 0.6 actually lands on blue. The golden masks encode this; changing it is Part 4 of the plan and re-baselines them.
- Bubbles are children of fish (`get_child_sprites()`); `Renderer.all_sprites()` flattens parents and children for both `animate()` and `render()`, so a sprite kind that is never drawn usually means it was not returned there.
