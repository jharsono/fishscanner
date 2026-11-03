# Progress (Gauntlet Loop)

Current target: Part 0 critic round 1; Part 1 build round 1
Completed parts: none signed off yet
Failed approaches (do not repeat):
- Mutation-testing the scanner by sed-editing source and restoring it within
  one second with same-length edits: stale .pyc kept the mutation alive.
  Always run with `python -B` / PYTHONDONTWRITEBYTECODE=1 and clear
  __pycache__ between mutations.
- Running parallel shell commands that mutate the same source file.
Evidence: tests/ on branch modernize/part-0-scanner-tests, 7 passed; dilate
2->1 fails both photos (2920/3884 px), C 3->4 fails fish1 (6521), red weight
0.6->0.5 fails fish2 (690); marker_size 110->80 passes (no effect, see Part 4).
Next action: Part 0 critic; build Part 1 in a worktree.
Remaining boundary: 3 critic rounds per part; approvals pending on Python
floor, requirements.txt, GL approach, XQuartz reference capture; no push.
