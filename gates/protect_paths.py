#!/usr/bin/env python3
"""PreToolUse gate: block edits to protected paths.

Patterns come from ``.fleet/protected-paths`` (one glob per line, ``#`` for
comments). Without that file, DEFAULT_PATTERNS apply. A pattern ending in
``/**`` protects a whole directory.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import (  # noqa: E402
    allow,
    block,
    load_patterns,
    matches_any,
    parse_args,
    project_root,
    read_event,
    relative_to_root,
)

DEFAULT_PATTERNS = [
    ".git/**",
    ".env",
    ".env.*",
    "secrets/**",
    "**/secrets/**",
    ".github/workflows/**",
    ".fleet/**",
]


def main() -> int:
    opts = parse_args(__doc__ or "")
    event = read_event()
    root = project_root(event)
    patterns = load_patterns(root, "protected-paths", DEFAULT_PATTERNS)

    for raw_path in event.paths():
        rel = relative_to_root(raw_path, root)
        hit = matches_any(rel, patterns)
        if hit:
            return block(
                f"Blocked: '{rel}' is protected by pattern '{hit}' in .fleet/protected-paths. "
                "Agents may not edit this path. If the change is required, stop and explain "
                "why in your summary so a human can make it.",
                opts.format,
            )
    return allow(opts.format)


if __name__ == "__main__":
    sys.exit(main())
