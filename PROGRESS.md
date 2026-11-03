# Progress (Gauntlet Loop)

Current target: Part 4 critic; PRs #16 (docs) and #17 (py3.14 pyright) awaiting merge; macOS CI runners time out in queue
Completed parts: Part 0 (critic PASS); Part 1 (critic conditional PASS, wheel fix applied); Part 3 (round 2 critic PASS, leftovers applied)
Failed approaches (do not repeat):
- Mutation-testing the scanner by sed-editing source and restoring it within
  one second with same-length edits: stale .pyc kept the mutation alive.
  Always run with `python -B` / PYTHONDONTWRITEBYTECODE=1 and clear
  __pycache__ between mutations.
- Running parallel shell commands that mutate the same source file.
- Mutation-checking an UNCOMMITTED fix by editing the file and restoring it
  with `git checkout`: that restores the committed version and discards the
  fix. Commit (or stash) first, mutate, then `git checkout` to restore.
- Chaining test -> commit -> push in one shell line without gating on the
  test result; it pushed a red commit once.
- Decoding JPEGs with cv2.imread in the ingestion path: a truncated
  progressive JPEG decodes to a full blurry frame with all markers, so
  size-settling alone let a stalled copy produce a fish from a half file.
  PIL refuses truncated files (OSError), so all decoding goes through PIL.
Evidence:
- Part 0: branch modernize/part-0-scanner-tests @ 27570b9, 7 passed; dilate
  2->1 fails both photos (2920/3884 px), C 3->4 fails fish1 (6521), red
  weight 0.6->0.5 fails fish2 (690); marker_size 110->80 passes (no effect).
- Part 1: branch modernize/part-1-packaging (stacked on Part 0); ruff check,
  ruff format --check, pyright, pytest all exit 0 locally; wheel contains
  main_ocean.py; CI not yet run (no push without approval). The spec item
  "GL-dependent tests marked and skipped headless" is satisfied vacuously:
  no GL tests exist and no marker config was added.
Deferred to later parts (not fixed yet): asset paths are CWD-relative and
engine/ and ocean/ lack __init__.py (Part 2); .DS_Store files are tracked in
git (pre-existing, unrelated to any part; needs Josh's OK to untrack).
- Part 3: branch modernize/part-3-ingestion (stacked on Part 1); engine/photos.py
  replaces watchdog with size-settled polling plus retry with backoff; all
  decoding goes through PIL so truncated JPEG/HEIC return None instead of a
  partial image or an escaping ValueError; 21 tests pass; all gates exit 0.
  Round 1 critic: FAIL (HEIC ValueError killed the watcher thread, no retry).
  Round 2 critic: PASS; afterwards the scanner golden fixture was switched to
  the app decoder, folder removal no longer kills the watcher, 22 tests pass.
  Known and documented: a file overwritten in place is not rescanned; a file
  given up on after 3 attempts stays ignored; marker-less photos are scanned
  3 times before give-up.
  Behaviour change to confirm with Josh: fish present at startup now appear
  over the first few frames (one per animation tick) instead of before the
  first frame, because startup and the watcher share one queue.
- Part 2: branch modernize/part-2-modern-gl (stacked on Part 3); glfw window
  with a 3.3 core forward-compatible context (macOS hands back 4.1), VAO
  meshes shared per grid size, GLSL 3.30 programs built from a per-sprite
  transform function, numpy matrices, Resources registry, fixed-step loop;
  34 tests pass including GL smoke tests in a hidden window; all gates exit 0;
  hidden-window screenshots of all three scenes look right. Critic round 1:
  conditional PASS; its largest gap (decoration textures leaked on every
  scene switch, ~100 MB per Ocean visit) is fixed by caching textures per
  file in Scene, with a test that fails against the uncached loader (54 vs
  21 textures). Fish wave is in world space on purpose (documented in the
  plan). Bubbles not rendering since commit 172395b was unintentional (Josh); fixed in Part 5.
Decisions 2026-11-03: XQuartz capture skipped (Josh ran Part 2 and judged
it good; A/B replaced by his check); window made resizable at his request
(cover camera beyond the backgrounds' aspect); bubbles restored.
Blocked on Josh: enabling workflows on the forked repo (Actions tab
button) so CI runs on the PRs; two new fish photos for Part 4; "go" for
Part 6 (docs, delete setup.sh/run.sh).
- Part 7: branch modernize/part-7-depth (stacked on Part 5); fish distance
  cycle (shrink to 45%, half speed, dim, z back). Critic round 1: FAIL, the
  far fish painted over the near one because the transparent pass drew
  nearest-first with depth writes off; fixed by drawing transparent sprites
  farthest-first, with a pixel test. Bubbles now inherit the fish's
  distance; a fish leaving from the far point exits at full pace. 55 tests.
  Critic round 2: PASS. Deferred nits: bubble scale z is shrunk along with
  x/y (harmless under the orthographic camera); a test spells np.abs as
  __abs__(). Fold into the next Part 7 amend if one happens.
- Part 8: branch modernize/part-8-tail-beat (stacked on Part 7); Josh found
  the y-sine body wave unnatural; replaced by a time-driven tail beat that
  foreshortens the tail horizontally and never moves it vertically.
- Part 9: branch modernize/part-9-turn-loop (stacked on Part 8); fish that
  began swimming beyond a border flipped every tick and spun in place (Josh
  saw it on fish 2); the bounce now requires an outward heading. Old code
  fails the new tests with 600 flips in 600 ticks. Critic round 1: PASS.
  Noted for a later part: a vertical-entry fish with the random horizontal
  nudge can start swimming up to |x| ~3.3, off screen for 8-12 s (0.2% of
  entries).
- Part 5: branch modernize/part-5-animation (stacked on Part 2); FixedStepClock
  extracted and tested (tick count identical at 30/60/144 Hz frames, stall
  cap), bubble removal no longer mutates the list it iterates (mutation
  check: old code fails the test), meshes created lazily on first render so
  sprite logic is testable without a GL context, unused ocean/debug.py
  deleted; child sprites (bubbles) are rendered again, which Josh confirmed
  had been lost unintentionally; 43 tests pass; all gates exit 0. The
  fixed-step loop itself landed in Part 2; Part 5 extracted and tested it.
  Critic round 1: PASS (30 vs 60 Hz identical, irregular frames within 0.3%).
- Part 4: branch modernize/part-4-scanner (from main); painted colour joins
  the stroke mask so cropped-outline fins stay opaque (fish2: 4028 leaked
  px -> 8); RGB unpack corrected; goldens re-baselined. Critic round 1:
  PASS with a robustness cliff under warm colour cast; fixed by making the
  paint threshold relative to the paper's saturation (border band), with a
  cast test. 65 tests; gates 0.
CI: Ubuntu cells pass. macOS cells are mostly cancelled by GitHub after
~15 min in queue with zero steps (two did run: 3.11 passed fully, 3.14 hit
the pyright issue fixed in PR #17). Decision needed: keep macOS in the
matrix and tolerate the queue, or drop it.
Next action: Part 4 critic; merge #17, rebase and merge #16, then the
integration critic on main.
Remaining boundary: 3 critic rounds per part (1 used on Parts 0 and 1, 2 on Part 3, 1 on Parts 2 and 5, 2 on Part 7, 1 on Part 9); approvals
pending on Python floor, requirements.txt, GL approach, XQuartz reference
capture, and pushing branches for CI; no push.
