"""Shared helpers for gate scripts.

Gates are plain Python (standard library only, 3.9+) so they run in sandboxed
environments with no network and no extra packages. Each gate reads a hook
payload as JSON on stdin and normalises the differences between agent tools:

* Claude Code (and Devin CLI, which uses Claude Code compatible hooks):
  ``tool_name`` / ``tool_input``; block by printing to stderr and exiting 2.
* GitHub Copilot (CLI and cloud agent): ``toolName`` / ``toolArgs``; block by
  printing ``{"permissionDecision": "deny", ...}`` to stdout and exiting 0.

Pass ``--format copilot`` to select Copilot output. The default is Claude.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

BLOCK_EXIT_CODE = 2
PATH_KEYS = ("file_path", "path", "filePath", "notebook_path", "target_file")
COMMAND_KEYS = ("command", "cmd", "script")


@dataclass
class HookEvent:
    tool_name: str = ""
    args: dict[str, Any] = field(default_factory=dict)
    stop_hook_active: bool = False
    cwd: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    def paths(self) -> list[str]:
        found = []
        for key in PATH_KEYS:
            value = self.args.get(key)
            if isinstance(value, str) and value:
                found.append(value)
        for edit in self.args.get("edits", []) or []:
            if isinstance(edit, dict) and isinstance(edit.get("file_path"), str):
                found.append(edit["file_path"])
        return found

    def command(self) -> str:
        for key in COMMAND_KEYS:
            value = self.args.get(key)
            if isinstance(value, str):
                return value
        return ""


def parse_args(description: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--format",
        choices=("claude", "copilot"),
        default=os.environ.get("FLEET_HOOK_FORMAT", "claude"),
        help="Hook protocol to answer in (default: claude).",
    )
    return parser.parse_args()


def read_event(stream=None) -> HookEvent:
    stream = stream or sys.stdin
    text = stream.read()
    try:
        data = json.loads(text) if text.strip() else {}
    except json.JSONDecodeError:
        data = {}
    if not isinstance(data, dict):
        data = {}

    tool_name = data.get("tool_name") or data.get("toolName") or ""
    args: Any = data.get("tool_input")
    if args is None:
        args = data.get("toolArgs")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except json.JSONDecodeError:
            args = {"command": args}
    if not isinstance(args, dict):
        args = {}

    return HookEvent(
        tool_name=str(tool_name),
        args=args,
        stop_hook_active=bool(data.get("stop_hook_active", False)),
        cwd=str(data.get("cwd") or ""),
        raw=data,
    )


def project_root(event: HookEvent | None = None) -> Path:
    for candidate in (
        os.environ.get("CLAUDE_PROJECT_DIR"),
        os.environ.get("FLEET_PROJECT_DIR"),
        event.cwd if event else None,
    ):
        if candidate:
            return Path(candidate).resolve()
    return Path.cwd().resolve()


def relative_to_root(path: str, root: Path) -> str:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        return candidate.resolve().relative_to(root).as_posix()
    except ValueError:
        return candidate.resolve().as_posix()


def load_patterns(root: Path, filename: str, defaults: list[str]) -> list[str]:
    config = root / ".fleet" / filename
    if not config.is_file():
        return list(defaults)
    patterns = []
    for line in config.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def matches_any(rel_path: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        if fnmatch.fnmatchcase(rel_path, pattern):
            return pattern
        if pattern.endswith("/**") and (rel_path == pattern[:-3] or rel_path.startswith(pattern[:-2])):
            return pattern
    return None


def allow(fmt: str) -> int:
    if fmt == "copilot":
        print(json.dumps({"permissionDecision": "allow"}))
    return 0


def block(message: str, fmt: str) -> int:
    if fmt == "copilot":
        print(json.dumps({"permissionDecision": "deny", "permissionDecisionReason": message}))
        return 0
    print(message, file=sys.stderr)
    return BLOCK_EXIT_CODE
