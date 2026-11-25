#!/usr/bin/env python3
"""PreToolUse gate: block dangerous shell commands.

Blocks force pushes, pushes to the default branch, history rewrites on shared
refs, skipping git hooks, deleting tags or remote branches, and recursive
deletes outside the working tree. Extra regexes can be added one per line in
``.fleet/blocked-commands``.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _common import allow, block, load_patterns, parse_args, project_root, read_event  # noqa: E402

RULES: list[tuple[str, str]] = [
    (r"\bgit\s+push\b[^\n;&|]*\s(--force(?!-with-lease)\b|-f\b)", "force push"),
    (r"\bgit\s+push\b[^\n;&|]*\s\+\S+", "force push via +refspec"),
    (r"\bgit\s+push\b[^\n;&|]*\s(origin\s+)?(HEAD:)?(main|master)\b(?!-)", "push to the default branch"),
    (r"\bgit\s+push\b[^\n;&|]*\s(--delete|-d)\b", "deleting a remote branch or tag"),
    (r"\bgit\s+push\b[^\n;&|]*\s:\S+", "deleting a remote ref"),
    (r"\bgit\s+tag\s+(-d|--delete)\b", "deleting a tag"),
    (r"--no-verify\b", "skipping git hooks"),
    (r"\bgit\s+reset\s+--hard\s+(origin/)?(main|master)\b", "hard reset onto the default branch"),
    (r"\bgit\s+filter-(branch|repo)\b", "rewriting history"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*f?[a-zA-Z]*\s+(/|~|\$HOME)(\s|$)", "recursive delete of / or home"),
    (r"\bchmod\s+-R\s+777\b", "world-writable permissions"),
    (r"\b(curl|wget)\b[^\n|]*\|\s*(sudo\s+)?(ba|z)?sh\b", "piping a download into a shell"),
]


def main() -> int:
    opts = parse_args(__doc__ or "")
    event = read_event()
    command = event.command()
    if not command:
        return allow(opts.format)

    root = project_root(event)
    extra = [
        (pattern, "a command listed in .fleet/blocked-commands")
        for pattern in load_patterns(root, "blocked-commands", [])
    ]

    for pattern, label in RULES + extra:
        if re.search(pattern, command):
            return block(
                f"Blocked: this command looks like {label}. Agents may not run it. "
                "Find another approach, or stop and ask a human.",
                opts.format,
            )
    return allow(opts.format)


if __name__ == "__main__":
    sys.exit(main())
