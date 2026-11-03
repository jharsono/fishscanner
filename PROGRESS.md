# Progress (Gauntlet Loop)

Current target: Part 2 critic round 1 (A/B against old-build references pending XQuartz install)
Completed parts: Part 0 (critic PASS); Part 1 (critic conditional PASS, wheel fix applied); Part 3 (round 2 critic PASS, leftovers applied)
Failed approaches (do not repeat):
- Mutation-testing the scanner by sed-editing source and restoring it within
  one second with same-length edits: stale .pyc kept the mutation alive.
  Always run with `python -B` / PYTHONDONTWRITEBYTECODE=1 and clear
  __pycache__ between mutations.
- Running parallel shell commands that mutate the same source file.
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
  hidden-window screenshots of all three scenes look right.
Blocked on Josh: XQuartz install (sudo) for old-build reference capture;
enabling workflows on the forked repo (Actions tab button) so CI runs on
PRs #7-#10; two new fish photos for Part 4.
Next action: Part 2 critic on everything judgeable without references; A/B
once references exist.
Remaining boundary: 3 critic rounds per part (1 used on Parts 0 and 1, 2 on Part 3, 0 on Part 2); approvals
pending on Python floor, requirements.txt, GL approach, XQuartz reference
capture, and pushing branches for CI; no push.
