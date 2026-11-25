#!/usr/bin/env python3
"""Stop gate: refuse to let the agent finish while checks are failing.

Runs the project's fast check command when the agent tries to stop. If it
fails, the tail of its output goes back to the agent as work to do (exit 2).

The command is the first of:
  1. ``$FLEET_TEST_CMD``
  2. the first line of ``.fleet/test-command``
  3. ``make test-fast`` if the Makefile defines that target

The gate skips when nothing changed (clean tree and no unpushed commits),
unless ``FLEET_GATE_ALWAYS=1``. It always lets go when the agent is already
continuing because of a previous Stop block, to avoid infinite loops.
"""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import BLOCK_EXIT_CODE, parse_args, project_root, read_event  # noqa: E402

TAIL_LINES = 60
DEFAULT_TIMEOUT = 600


def resolve_command(root: Path) -> list[str] | None:
    env_cmd = os.environ.get("FLEET_TEST_CMD", "").strip()
    if env_cmd:
        return shlex.split(env_cmd)
    config = root / ".fleet" / "test-command"
    if config.is_file():
        for line in config.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                return shlex.split(line)
    makefile = root / "Makefile"
    if makefile.is_file() and re.search(r"^test-fast\s*:", makefile.read_text(encoding="utf-8"), re.M):
        return ["make", "test-fast"]
    return None


def has_changes(root: Path) -> bool:
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return True
    if git("status", "--porcelain").stdout.strip():
        return True
    ahead = git("rev-list", "--count", "@{upstream}..HEAD")
    if ahead.returncode == 0:
        return ahead.stdout.strip() not in ("", "0")
    branch = git("rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    return branch not in ("main", "master", "HEAD")


def main() -> int:
    parse_args(__doc__ or "")
    event = read_event()
    if event.stop_hook_active:
        return 0

    root = project_root(event)
    if os.environ.get("FLEET_GATE_ALWAYS") != "1" and not has_changes(root):
        return 0

    command = resolve_command(root)
    if command is None:
        print(
            "require_green: no check command configured (set FLEET_TEST_CMD, "
            ".fleet/test-command, or a Makefile test-fast target). Skipping.",
            file=sys.stderr,
        )
        return 0

    timeout = int(os.environ.get("FLEET_TEST_TIMEOUT", DEFAULT_TIMEOUT))
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        print(
            f"Checks timed out after {timeout}s: {' '.join(command)}. Make them faster or fix the hang.",
            file=sys.stderr,
        )
        return BLOCK_EXIT_CODE
    except FileNotFoundError:
        print(f"require_green: could not run {command[0]!r}. Skipping.", file=sys.stderr)
        return 0

    if result.returncode == 0:
        return 0

    output = (result.stdout + result.stderr).strip().splitlines()[-TAIL_LINES:]
    print(
        f"Checks are failing ({' '.join(command)} exited {result.returncode}). Fix them before finishing:",
        file=sys.stderr,
    )
    print("\n".join(output), file=sys.stderr)
    return BLOCK_EXIT_CODE


if __name__ == "__main__":
    sys.exit(main())
