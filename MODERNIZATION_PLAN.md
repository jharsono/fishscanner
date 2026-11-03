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

Decision 2026-11-03: Josh skipped the XQuartz capture after running the Part 2
build himself and judging it good ("part 2 looks good"). His visual check
stands in for the blind A/B in Parts 2 and 5; critics compare against the
README screenshot and the raw assets instead. The capture steps below are
kept for the record only.

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
Trigger: Josh saw transparent holes in the top fins of `example_fish2`
(2026-11-03). Root cause: those fins reach the line between the top markers,
so the crop removes their outline stroke; the mask came from ink strokes
only (adaptive threshold ignores flat colour) and filled the inside of the
outline, so where the outline was missing the fill leaked.
Builder: count painted colour (HSV saturation and value above a threshold)
as drawing in addition to strokes, so filled areas stay opaque with or
without their outline; correct the RGB-as-BGR unpack so the 0.6 weight
really lands on red (found by the Part 6 critic); re-baseline the goldens.
Measured: example 1 unchanged by the colour mask, example 2 goes from 4028
painted-but-transparent pixels to 8; the unpack fix moves ~250 boundary
pixels per photo. The fixed 110 px corner masks have no effect on either
example (the largest contour never reaches a corner) but guard a drawing
that touches a marker, so they stay. Not done: a soft alpha edge (taste
call; the hard edge has not been raised as a problem) and warping with a
margin (it brings the table into frame, which can become the largest
contour).
Round 1 critic found a cliff: an absolute saturation threshold turns the
whole page into "paint" under a warm colour cast (paper median S > 60,
simulated with a 25% blue deficit: IoU 0.55). The threshold is now
relative to the paper's saturation, measured from the blank border of the
aligned frame, plus a margin of 50; under a 35% blue deficit the mask
stays within IoU 0.9999 of the golden, and a test covers a 30% cast.
Critic: the painted-leak test fails on the old code for example 2 and
passes now; both goldens re-baselined and reviewed as images; a photo with
a drawing that touches a corner marker still yields the fish; the
colour-cast test fails against an absolute threshold.
Success: tests pass and Josh sees solid fins in the app.

### Part 5: Animation and engine hygiene  (depends on Part 2)
Builder: delta-time movement from the frame clock; dead-fish and bubble
removal build new lists instead of removing during iteration;
`ocean/debug.py` is either wired to a real debug overlay or deleted. (The
fish-shader wave fix landed in Part 2.) Bubbles had not been drawn since
commit 172395b "Fix collisions" because `Renderer.render` no longer walked
child sprites; Josh confirmed that was unintentional (2026-11-03) and Part 5
restores child rendering.
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

### Part 7: Fish swim into the distance  (depends on Part 5; requested by Josh 2026-11-03)
Builder: each swimming fish follows a slow cosine distance cycle with a
random period (10-25 s). At the far point it is drawn at 45% of its size,
moves at half pace, is tinted down to 70% and sits at z = -0.5 so nearer
fish draw in front; it then grows back to its original size. The cycle
starts at zero distance when the entry animation ends, so there is no
jump; facing direction is kept apart from scale so shrinking never flips a
fish.
Critic: headless tests for the cycle, size return, facing and
slower/dimmer/behind at the far point; a rendered contact sheet across one
cycle with two fish out of phase, judged for a convincing "into the
distance" look and for the far fish drawing behind the near one.
Success: tests pass and Josh judges the motion natural in the running app.

### Part 8: Side-view tail beat  (depends on Part 7; requested by Josh 2026-11-03)
Josh found the y-sine body wave unnatural: it read as the fish flapping
vertically. Builder: replace it with a time-driven tail beat seen from the
side: the swing grows toward the tail tip, travels along the body and
foreshortens the tail horizontally (the tail swings out of the picture
plane), never moving it vertically; per-fish phase offset so fish do not
beat in unison. A continuous `time` uniform (seconds) reaches every program.
Critic: a GL test that the fish silhouette's height is constant across a
beat while its width changes; a contact sheet across one beat; the seaweed
sway must be unchanged.
Success: tests pass and Josh judges the motion natural in the running app.

### Part 9: Turning loop at the borders  (bug Josh saw 2026-11-03)
A fish that starts swimming already beyond a border (a long entry animation
overshoots it) flipped its heading every tick, because the bounce checked
position only; it oscillated in place while re-arming the y-rotation, so it
spun on the spot. Builder: bounce only when beyond a border and still
heading outward, for x and y; tests place a swimming fish past each border
heading out and assert exactly one turn and a return inside.
Critic: run the tests against the old bounce (must fail with hundreds of
flips); drive many seeded fish through full entry animations and confirm
none spins more than once per wall contact.

### Part 10: Temperament  (requested by Josh 2026-11-03)
Josh: "the tail animation should have more ebb-and-flow, uniqueness per
fish, and fish should move at different speeds and oscillate between slow
and fast depending on their objective (hunting or fleeing)."
Builder: each fish gets a random `tempo` (0.8-1.25) scaling its speed and
tail beat; an `effort` level that drifts between rest (0.45), cruise (1.0)
and burst (1.9), re-chosen every 2-7 s and eased over about a second; speed
= vector x distance factor x effort; the tail beat phase is accumulated per
fish from tempo and effort and passed to the shader through a new
per-sprite `params` uniform (phase, peak swing), replacing the global clock
phase; a fish told to leave bursts (flees).
Critic: headless tests for distinct tempos, bounded and eased effort that
actually changes, speed and beat following effort, fleeing; a GL test that
the beat still only foreshortens; a 30 s simulation showing fish out of
phase and at different efforts.
Success: tests pass and Josh judges the variety natural in the app.

### Part 11: No passing through each other  (requested by Josh 2026-11-03)
Josh: "sometimes there's a collision on the z axis and a fish goes through
another fish; ensure there's no collision before a fish goes to the next z."
Builder (round 2; round 1 paused the whole cycle of every overlapping
fish, and the critic showed that at 6+ fish in a 3x1 band that froze the
near/far feature entirely): hold only the crossing. Each tick
`prevent_depth_crossings` lets a fish's depth step through unless it would
meet or pass the depth of a fish whose painted rectangle it overlaps, now
or after this tick's movement (positions and sizes looked ahead one step);
whichever fish of the pair would do the crossing is held, the other keeps
cycling. Overlap uses the smallest centred box that contains the scan's paint
(`main_ocean.painted_extent`; the drawing can sit anywhere on the page and
is mirrored when the fish faces left, so the box must reach it from the
centre; ~0.8 x 1.0 of the canvas on the examples). Measured over 5 minutes
with 10 fish (the cap): 0 crossings on three seed sets in list and
shuffled order, every fish completes 2+ cycles, held 65-75% of swimming
ticks on average (worst fish up to 90%, single holds up to 2.5 minutes
while two fish travel together); with 3-5 fish, 30-45%. At equal depth the
fish the renderer draws on top (earlier in the list) is the one held, so
the order that forms matches the screen.
Critic: headless tests for overlap geometry (extent, look-ahead), for
cycling-until-the-crossing and resume, and a 6-fish minute with zero
crossings; the 10-fish 5-minute acceptance above reproduced.
Success: tests pass and Josh no longer sees fish pass through each other.

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
3. `requirements.txt`: dropped in Part 6; it had drifted from pyproject.toml.
4. One-time XQuartz install for reference capture: approved. The cask's
   `.pkg` needs sudo, so Josh runs `brew install --cask xquartz` himself.
5. Pushing branches and opening PRs: approved.
6. Part 4 photos: Josh tested with his own photo ("it works well") and
   reported the example 2 fin holes; no new photos were added to the repo.
7. XQuartz reference capture: skipped; Josh's visual check of the Part 2
   build replaces the A/B.
8. Bubbles not rendering was unintentional; restored in Part 5.
