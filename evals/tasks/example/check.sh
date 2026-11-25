#!/usr/bin/env bash
# Hidden check for the example task. Replace with the tests from the real fix.
# Runs inside the task worktree after the agent finishes; exit 0 means pass.
set -euo pipefail
python3 - <<'PY'
from mypkg.text import slugify  # replace with your module

assert slugify("Hello,  World!") == "hello-world"
assert slugify("a -- b") == "a-b"
print("ok")
PY
