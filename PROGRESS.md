# Progress (Gauntlet Loop)

Current target: Part 3 build round 1
Completed parts: Part 0 (critic PASS, tolerance fix applied); Part 1 (critic conditional PASS, wheel fix applied)
Failed approaches (do not repeat):
- Mutation-testing the scanner by sed-editing source and restoring it within
  one second with same-length edits: stale .pyc kept the mutation alive.
  Always run with `python -B` / PYTHONDONTWRITEBYTECODE=1 and clear
  __pycache__ between mutations.
- Running parallel shell commands that mutate the same source file.
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
Next action: build Part 3 (ingestion) on a branch stacked on Part 1.
Remaining boundary: 3 critic rounds per part (1 used on Parts 0 and 1); approvals
pending on Python floor, requirements.txt, GL approach, XQuartz reference
capture, and pushing branches for CI; no push.
