# FishScanner Modernization Plan (Gauntlet Loop)

Structured per the builder-vs-critic "Gauntlet Loop" pattern: a design card
(Objective / Metric / Boundary), work split into independently judgeable parts,
fresh-context critics that judge the real artifact against a concrete reference,
a persisted progress file, and a final integration pass.

"Modern industry standard" is interpreted here as: installs with one command on
a stock Mac, no X11; reproducible dependencies; linted and type-checked; tested
against real photos in CI; and code that a new contributor can read without
tribal knowledge. It does not mean swapping the proven classical CV pipeline
for ML, and it does not mean a full OpenGL rewrite (see Boundaries).

## Design card

**Objective (the state that must become true)**
A fresh clone on a stock Apple Silicon Mac runs with `uv sync && uv run
fishscanner`, with no XQuartz, no freeglut, no `DISPLAY` export and no logout.
Dropping a JPG, JPEG or HEIC into `photos/` (any case, including a file still
being copied) produces a swimming fish within 5 seconds. `ruff`, `pyright` and
`pytest` pass locally and in GitHub Actions on macOS and Ubuntu.

**Metric (evidence a critic can inspect directly)**
- Scanner: golden alpha masks for `photos/example_fish1.jpg` and
  `example_fish2.jpg`; IoU against golden ≥ 0.99 unless a part is explicitly
  allowed to change the mask, in which case a blind A/B of the cutouts.
- Rendering: screenshots of all three scenes captured from the running app,
  compared blind against reference screenshots captured from the current GLUT
  build before any change.
- Ingestion: pytest that copies a photo into a temp `photos/` dir in chunks
  with delays and asserts exactly one fish texture is queued.
- Animation: fish traversal time left-to-right measured at 30 Hz and 60 Hz
  must agree within 10%.
- Tooling: exit codes of `ruff check`, `pyright`, `pytest`, and the CI run URL.

**Boundary**
- Allowed: new files under `tests/`, `.github/`, `pyproject.toml`; edits to
  `engine/`, `ocean/`, `main_ocean.py`, docs.
- Forbidden without Josh's approval: ML background-removal dependencies;
  any backward-compatibility shim; deleting `setup.sh` / `run.sh` before
  Part 2 passes; merging. Pushing branches and opening PRs was approved on
  2026-11-03 so CI can run.
- Attempt cap: 3 critic rounds per part, then stop and escalate with the
  failed approaches listed. A repeated failure must come back with a changed
  strategy, not a retry.
- Each part is its own branch and PR with exactly one commit; squash after
  every critic round. One owner per coupled system
  (`main_ocean.py` is coupled to Parts 2, 3 and 5, so those run sequentially).

## Reference for quality (the bar)

Capture these BEFORE any code changes, in one setup session that Josh
approves because it installs system packages:
1. Install XQuartz + freeglut once, run the current app, screenshot each scene
   (`refs/scene_ocean.png`, `refs/scene_2.png`, `refs/scene_3.png`) with the
   two example fish loaded.
2. Dump the current scanner alpha masks for both example photos to
   `tests/golden/`.
3. Record a 10-second screen capture of fish motion for the animation A/B.
Then uninstall XQuartz so every later run proves the no-X11 objective.

## Parts, in dependency order

Independent parts may run in parallel. A part's critic receives only: this
file's section for the part, the reference, and the artifact. Never the
builder's reasoning.

### Part 0: Golden fixtures and scanner regression test  (prerequisite)
Builder: add `tests/test_scanner.py` using the two example photos; store golden
masks; assert at most 100 differing alpha pixels (the pipeline is
deterministic; a one-pixel boundary shift changes ~3000) and output shape
`(600, 800, 4)`.
Critic: run the test; confirm fixtures are the real photos, not synthetic;
confirm a deliberate one-pixel boundary change (dilate iterations 2→1) and a
colour-weight change both make the test fail.
Success: red/green demonstrated both ways.

### Part 1: Packaging, lint, types, CI  (prerequisite; independent of Part 0)
Builder: `pyproject.toml` with `uv` lock, `requires-python >= 3.11`, drop
`numpy<2` and `opencv<5` pins (verified working on OpenCV 5.0.0 / numpy 2.5.4
/ Python 3.14.5), console script `fishscanner`; `ruff` and `pyright` configs;
GitHub Actions matrix (macos-latest, ubuntu-latest) running ruff, pyright,
pytest. GL-dependent tests marked and skipped headless.
Critic: fresh clone in a temp dir, `uv sync`, run the three tools; inspect the
CI run page, not the summary. Confirm no `venv/` or `requirements.txt` is
needed.
Success: all three exit 0 locally and in CI. Gate: Josh approves the Python
floor and whether `requirements.txt` is kept for the README's manual path.

### Part 2: Replace GLUT with glfw and rewrite rendering on modern OpenGL  (depends on Parts 0, 1 and the references)
Josh chose the modern-GL rewrite over keeping legacy GL in a 2.1 context
(decision 2026-11-03).
Builder: window creation, main loop, keyboard (ESC, Left, Right) and the 60 Hz
tick move to glfw with an OpenGL 3.3 core, forward-compatible context (the
newest profile macOS offers is 4.1 core; no compatibility profile exists).
All fixed-function calls go: `Drawing` keeps its mesh in a VAO with one VBO
of positions and texture coordinates and builds its model matrix in numpy
from `position`/`rotate`/`scale`; `Renderer` owns the orthographic
projection and passes a model-view-projection matrix, the sprite colour and
the `timer` uniform to GLSL 3.30 shaders; a fragment shader samples the
texture, multiplies by colour and discards fragments with alpha below 0.1 in
place of `GL_ALPHA_TEST`. The fish and seaweed vertex shaders keep their
sine-wave displacement, both applied before projection: the seaweed wave in
sprite space (it is driven by the timer), the fish wave in world space,
because the fish shader has no timer term and only animates as the fish
moves through the wave; a sprite-space fish wave would be a static bend.
The old fish shader displaced in clip space, so Part 5's fix lands here. If
the A/B shows the body wiggle busier than the reference, the wave frequency
is per world unit where the old one was per clip unit (a factor of the
window aspect).
Two-pass opaque/transparent rendering, depth test and blending are kept.
`cleanup_and_exit` becomes a resource registry object instead of attributes
on a function. Asset paths (`ocean/images/...`) are resolved relative to the
package, not the working directory, so the `fishscanner` console script works
from any directory; `engine/` and `ocean/` get `__init__.py` files.
Critic: on a machine with no XQuartz, `uv run fishscanner`; blind A/B of
screenshots per scene vs `refs/`; arrows cycle scenes; ESC exits 0; no GL
errors logged. Also run on Ubuntu with Xvfb for the CI smoke test.
Success: A/B judged equal or better on all three scenes with the critic
naming any gap. Gate: Josh approves removing `setup.sh`, `run.sh`, the
XQuartz docs, and the `DISPLAY` lines.

### Part 3: Photo ingestion robustness  (depends on Part 0; independent of Part 2)
Builder: one `load_photo(path)` used by both startup scan and the watcher
(today the HEIC/JPG branch is duplicated); case-insensitive `.jpg/.jpeg/.heic`
in both paths; watcher reacts to file-closed or moved-in events, and retries a
read that returns `None` with backoff before giving up and logging.
Critic: run the chunked-copy pytest and an AirDrop-style `cp` of a 4 MB HEIC
into a live `photos/` dir; count fish; confirm `IMG_0001.JPG` loads at
startup.
Success: exactly one fish per file, every extension/case, no duplicate.

### Part 4: Scanner refinements  (depends on Part 0; independent of 2 and 3)
Builder: the fixed 110 px corner masks have zero effect on either example
photo (measured 2026-11-03: the largest contour never reaches the corners),
so first decide with evidence whether that code is needed at all, and delete
it if not; keep a soft alpha edge (no hard 127 threshold) so the GL alpha
test antialiases. The chopped top fin in `example_fish2` is caused by the
warp cropping at the line between the top markers, not by the corner mask;
fix by warping with a margin outside the marker rectangle.
Critic: blind A/B of cutouts vs the current goldens on both examples plus two
new photos Josh supplies; the chopped fin must be fixed; no new halo. Golden
test is then re-baselined with Josh's OK.
Success: A/B win on every photo. No ML dependencies (Boundary).

### Part 5: Animation and engine hygiene  (depends on Part 2)
Builder: delta-time movement from the frame clock; dead-fish and bubble
removal build new lists instead of removing during iteration;
`ocean/debug.py` is either wired to a real debug overlay or deleted. (The
fish-shader wave fix landed in Part 2.) Open question for Josh: bubbles have
not been drawn since commit 172395b "Fix collisions" because `Renderer.render`
no longer walks child sprites; restore child rendering in Part 5 or delete
the bubble code.
Critic: 30 Hz vs 60 Hz traversal timing within 10%; blind A/B of the motion
capture vs `refs/`; `grep` confirms no in-loop `.remove(`.
Success: timing metric met and A/B equal or better.

### Part 6: Documentation  (depends on Parts 2 and 3)
Builder: README install section becomes the one-command flow; delete the
camera section from `TROUBLESHOOTING.md` (no camera code exists); update
`CLAUDE.md` commands and architecture; keep the template and drawing
instructions.
Critic: a fresh reader follows README only, on a clean Mac, and gets a
swimming fish. Every command in the docs is executed, not read.

## Integration critic (final, fresh context)

Fresh clone, `uv sync`, `uv run fishscanner`, drop one JPG and one HEIC,
cycle all scenes, ESC. Then `ruff check`, `pyright`, `pytest`, and the CI URL.
Reports the single largest remaining gap, with evidence, or signs off.

## Progress file

`PROGRESS.md` at repo root (gitignored or committed, Josh's call), updated
after every round:

```
Current target: Part N, round k
Completed parts: ...
Failed approaches (do not repeat): ...
Evidence links: test output, screenshots, CI URLs
Next action: ...
Remaining boundary: rounds left on this part, approvals still needed
```

## Stop conditions

Stop and hand back to Josh when: the integration critic signs off; a part
exhausts 3 rounds; the same failure recurs without a new strategy; a change
would need a forbidden action; or a critic cannot judge without a human
(for example, taste calls on the soft-alpha edge or on fish motion feel).
"Until perfect" is not a stop condition.

## Decisions from Josh (2026-11-03)

1. Rendering: modern-GL rewrite, not legacy GL in a 2.1 context.
2. Python floor: 3.11.
3. `requirements.txt`: kept for now (not yet ruled on).
4. One-time XQuartz install for reference capture: approved. The cask's
   `.pkg` needs sudo, so Josh runs `brew install --cask xquartz` himself.
5. Pushing branches and opening PRs: approved.
6. Part 4 photos: Josh supplies two new fish photos.
