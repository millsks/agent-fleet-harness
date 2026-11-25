#!/usr/bin/env python3
"""Generate GitHub Copilot adapters from the canonical Claude Code files.

Writes, under adapters/copilot/:
  .github/agents/<name>.agent.md   one Copilot custom agent per .claude/agents/*.md
  .github/hooks/agent-fleet.json   preToolUse hooks that call the shared gates

Claude-only frontmatter (model, maxTurns, isolation, memory, ...) is dropped:
Copilot cloud agent does not support it. Tool names are mapped to Copilot's
primary aliases. Run with --check in CI to fail when the adapters are stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _frontmatter  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = ROOT / ".claude" / "agents"
OUT_DIR = ROOT / "adapters" / "copilot" / ".github"
GATES_PATH = ".fleet/gates"

# Claude Code tool name -> Copilot custom agent tool alias.
TOOL_MAP = {
    "Read": "read",
    "NotebookRead": "read",
    "Edit": "edit",
    "MultiEdit": "edit",
    "Write": "edit",
    "NotebookEdit": "edit",
    "Grep": "search",
    "Glob": "search",
    "Bash": "execute",
    "Agent": "agent",
    "Task": "agent",
    "WebFetch": "web",
    "WebSearch": "web",
    "TodoWrite": "todo",
}


def copilot_tools(tools: list[str], disallowed: list[str]) -> list[str]:
    blocked = {TOOL_MAP.get(t, t) for t in disallowed}
    result: list[str] = []
    for tool in tools:
        alias = TOOL_MAP.get(tool)
        if alias and alias not in result and alias not in blocked:
            result.append(alias)
    return result


def render_agent(path: Path) -> tuple[str, str]:
    doc = _frontmatter.load(path)
    name = str(doc.meta["name"])
    meta: dict[str, object] = {"name": name, "description": doc.meta["description"]}
    tools = doc.meta.get("tools")
    if isinstance(tools, list):
        meta["tools"] = copilot_tools(tools, list(doc.meta.get("disallowedTools") or []))
    notice = (
        f"<!-- Generated from .claude/agents/{path.name} by scripts/sync_adapters.py. "
        "Edit the source file and run `make sync`. -->\n\n"
    )
    return f"agents/{name}.agent.md", _frontmatter.dump(meta, notice + doc.body)


def render_hooks() -> str:
    def gate(script: str) -> dict[str, object]:
        return {
            "type": "command",
            "bash": f"python3 {GATES_PATH}/{script} --format copilot",
            "timeoutSec": 30,
        }

    config = {
        "version": 1,
        "hooks": {"preToolUse": [gate("protect_paths.py"), gate("guard_commands.py")]},
    }
    return json.dumps(config, indent=2) + "\n"


def expected_files() -> dict[str, str]:
    files = dict(render_agent(p) for p in sorted(AGENTS_DIR.glob("*.md")))
    files["hooks/agent-fleet.json"] = render_hooks()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="exit 1 if adapters are out of date")
    opts = parser.parse_args()

    expected = expected_files()
    existing = (
        {p.relative_to(OUT_DIR).as_posix() for p in OUT_DIR.rglob("*") if p.is_file()} if OUT_DIR.exists() else set()
    )

    stale = sorted(
        rel
        for rel, content in expected.items()
        if not (OUT_DIR / rel).is_file() or (OUT_DIR / rel).read_text(encoding="utf-8") != content
    )
    extra = sorted(existing - set(expected))

    if opts.check:
        if stale or extra:
            for rel in stale:
                print(f"stale: adapters/copilot/.github/{rel}")
            for rel in extra:
                print(f"unexpected: adapters/copilot/.github/{rel}")
            print("Adapters are out of date. Run `make sync` and commit the result.")
            return 1
        print(f"Copilot adapters up to date ({len(expected)} files).")
        return 0

    for rel in extra:
        (OUT_DIR / rel).unlink()
    for rel, content in expected.items():
        target = OUT_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    print(f"Wrote {len(expected)} files to adapters/copilot/.github/ ({len(stale)} changed, {len(extra)} removed).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
