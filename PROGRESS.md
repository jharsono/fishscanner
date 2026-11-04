# Progress (Gauntlet Loop)

Current target: Part 13 and 14 critics; PRs #20-#24 await merge
Completed parts: 0, 1, 2, 3, 4, 5, 7, 8, 9 merged to main on 2026-11-03; 6 merging
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
CI: workflows only run once the workflow file is on the default branch;
the merges to main queued the first runs (no fork "enable" button was
needed). Still blocked on Josh: two new fish photos for Part 4.
- Part 6: branch modernize/part-6-docs; README and TROUBLESHOOTING rewritten
  for uv + glfw, setup.sh/run.sh/requirements.txt deleted, CLAUDE.md
  architecture rewritten for Parts 7-9. Critic round 1: PASS; its finding
  that the scanner weights blue where it says red is parked for Part 4.
  Tracked .DS_Store files untracked so the new ignore rule applies.
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
- Part 10: branch modernize/part-10-temperament (from main); per-fish tempo,
  rest/cruise/burst effort with eased transitions, tail phase and swing per
  fish through a new `params` uniform. Critic round 1: PASS; its leftovers
  applied: unused `time` uniform plumbing removed, a re-pick always changes
  gear, beat damping documented. 71 tests; gates 0. Josh reported "fish
  didn't seem to load" on this branch; headless startup from the same
  folder loads all three photos (including his 4032x3024 IMG_3348.JPG, scan
  0.16 s) and renders them, so not reproduced; awaiting details.
- Part 11: branch modernize/part-11-no-pass-through (stacked on Part 10).
  Round 1 critic: FAIL (pausing every overlapping fish froze the depth
  cycle at 6+ fish: 99.7% held, no cycle completed). Round 2: hold only
  the crossing, with look-ahead of positions and sizes and painted extents
  from the scan; 10 fish x 5 min x 3 seeds: 0 crossings, 3+ cycles each,
  ~60% held (30-45% at 3-5 fish). Round 2 critic: narrow FAIL: the extent
  box was centred on the sprite while the paint can sit anywhere on the
  page; now the smallest centred box containing the paint; eased effort in
  the look-ahead; equal-depth tie holds one fish; look-ahead tests. 79 tests.
  Round 3 critic (last): PASS; found the tie held the wrong fish (the one
  drawn on top stepped behind: a one-off pop for pairs entering together);
  now the top-drawn fish is held. Eased-effort look-ahead test added.
- Part 12: branch modernize/part-12-fluid-turns (stacked on Part 11);
  heading-based steering replaces the velocity flip: arcs at walls with a
  committed turn direction, gentle wander, levelling, facing from heading.
  Round 1 critic: FAIL: the tie-break was a heading-change sign, which
  curves toward the middle at the right wall but away at the left (loops
  past the top/bottom by 0.2); now chosen in the heading's frame, with a
  test that fails on the inverted sign; vertical margin 0.2 for bursts.
  8 fish x 5 min after warm-up: overshoot 0 on three sides, 0.09 bottom.
  Round 2 critic: PASS with a regression it caught: go_away doubled vx,
  which under steering can be ~0 mid-turn, leaving a culled fish hovering
  forever; it now leaves level at double speed along its sideways or
  facing direction and keeps facing while leaving (exits from every
  heading within 4 s). Burst test tightened; top/bottom tie test added.
  Round 3 critic (last): PASS (1728-case exit sweep, all leave within 7 s).
  88 tests; gates 0.
- Part 13: branch modernize/part-13-ease-in-out (stacked on Part 12); entry
  speed decays toward a cruising speed chosen at entry and carries into
  swimming unchanged; exit ramps to double speed. Critic round 1: PASS;
  its gap (half the vertical entries came in dead vertical, so the facing
  was a coin flip and a fish could dive for 9 s) fixed: vertical entries
  always angled, levelling and facing run during the entry, a culled
  entrant settles to a normal exit pace. 100 tests; gates 0.
- Part 14: branch modernize/part-14-head-turn (stacked on Part 13); the head
  end foreshortens by the eased depth rate, same mechanism as the tail.
  Critic round 1: PASS; its gap (the head froze at its angle for the whole
  exit) fixed: the head eases straight while leaving. 104 tests; gates 0.
Part 4 round 2 critic: PASS (cast sweep never breaks). Noted for a small
follow-up: the corner mask leaves a ~20 px ring of a touched marker; two
comment wordings in simplescanner.py overstate paper noise and a blank
border.
Next action: Part 10 critic; integration critic verdict.
Remaining boundary: 3 critic rounds per part (1 used on Parts 0 and 1, 2 on Part 3, 1 on Parts 2 and 5, 2 on Part 7, 1 on Part 9, 1 on Part 6, 2 on Part 4, 2 on Part 11, 2 on Part 12); approvals
pending on Python floor, requirements.txt, GL approach, XQuartz reference
capture, and pushing branches for CI; no push.
