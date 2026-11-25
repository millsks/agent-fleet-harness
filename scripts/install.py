#!/usr/bin/env python3
"""Install the agent fleet harness into another repository.

Copies agents, skills, gates and starter config into TARGET. Existing files are
left alone unless --force is given; existing .claude/settings.json hooks are
merged, not replaced. Nothing is committed: review the diff in TARGET.

Examples:
  python3 scripts/install.py ../my-service
  python3 scripts/install.py ../my-service --with copilot --workflows
  python3 scripts/install.py ../my-service --models inherit --dry-run
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATES_DEST = ".fleet/gates"


class Installer:
    def __init__(self, target: Path, force: bool, dry_run: bool) -> None:
        self.target = target
        self.force = force
        self.dry_run = dry_run
        self.written: list[str] = []
        self.skipped: list[str] = []

    def write(self, rel: str, content: str) -> None:
        dest = self.target / rel
        if dest.exists() and not self.force:
            self.skipped.append(rel)
            return
        self.written.append(rel)
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content, encoding="utf-8")

    def copy(self, src: Path, rel: str) -> None:
        dest = self.target / rel
        if dest.exists() and not self.force:
            self.skipped.append(rel)
            return
        self.written.append(rel)
        if not self.dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)

    def copy_tree(self, src_dir: Path, rel_dir: str, skip: tuple[str, ...] = ()) -> None:
        for src in sorted(src_dir.rglob("*")):
            if src.is_file() and not any(part in skip for part in src.parts) and "__pycache__" not in src.parts:
                self.copy(src, f"{rel_dir}/{src.relative_to(src_dir).as_posix()}")


def agent_text(path: Path, models: str | None) -> str:
    text = path.read_text(encoding="utf-8")
    if models:
        text = re.sub(r"^model:.*$", f"model: {models}", text, count=1, flags=re.M)
    return text


def merged_settings(target: Path) -> tuple[str, bool]:
    """Return target settings.json with harness hooks merged in, and whether it changed."""
    source = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    source_text = json.dumps(source).replace("$CLAUDE_PROJECT_DIR/gates/", f"$CLAUDE_PROJECT_DIR/{GATES_DEST}/")
    ours = json.loads(source_text)

    dest = target / ".claude" / "settings.json"
    current = json.loads(dest.read_text(encoding="utf-8")) if dest.is_file() else {}
    hooks = current.setdefault("hooks", {})
    changed = not dest.is_file()
    for event, groups in ours["hooks"].items():
        existing = hooks.setdefault(event, [])
        present = {h.get("command") for g in existing for h in g.get("hooks", [])}
        for group in groups:
            if not all(h.get("command") in present for h in group["hooks"]):
                existing.append(group)
                changed = True
    return json.dumps(current, indent=2) + "\n", changed


def harness_version() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True)
    sha = result.stdout.strip() if result.returncode == 0 else "unknown"
    return f"agent-fleet-harness {sha}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("target", type=Path, help="path to the repository to install into")
    parser.add_argument("--with", dest="extras", default="", help="comma-separated adapters to add: copilot")
    parser.add_argument("--workflows", action="store_true", help="also copy GitHub Actions workflow templates")
    parser.add_argument(
        "--models", choices=("inherit",), help="rewrite every agent's model (use where model aliases are not allowed)"
    )
    parser.add_argument("--force", action="store_true", help="overwrite files that already exist")
    parser.add_argument("--dry-run", action="store_true", help="show what would change without writing")
    opts = parser.parse_args()

    target = opts.target.resolve()
    if not target.is_dir():
        parser.error(f"{target} is not a directory")
    if target == ROOT:
        parser.error("refusing to install the harness into itself")
    extras = {e.strip() for e in opts.extras.split(",") if e.strip()}
    unknown = extras - {"copilot"}
    if unknown:
        parser.error(f"unknown adapter(s): {', '.join(sorted(unknown))}")

    inst = Installer(target, opts.force, opts.dry_run)

    for path in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        inst.write(f".claude/agents/{path.name}", agent_text(path, opts.models))
    inst.copy_tree(ROOT / ".claude" / "skills", ".claude/skills")
    for path in sorted((ROOT / "gates").glob("*.py")):
        inst.copy(path, f"{GATES_DEST}/{path.name}")
    inst.copy_tree(ROOT / "templates" / "fleet", ".fleet")
    inst.copy(ROOT / "templates" / "AGENTS.md", "AGENTS.md")
    inst.copy(ROOT / "templates" / "CLAUDE.md", "CLAUDE.md")
    inst.copy(ROOT / "evals" / "run.sh", "evals/run.sh")
    inst.copy(ROOT / "evals" / "README.md", "evals/README.md")
    inst.copy_tree(ROOT / "evals" / "tasks" / "example", "evals/tasks/example")
    inst.write(".fleet/harness-version", harness_version())

    settings, changed = merged_settings(target)
    if changed:
        inst.written.append(".claude/settings.json (hooks merged)")
        if not opts.dry_run:
            (target / ".claude").mkdir(parents=True, exist_ok=True)
            (target / ".claude" / "settings.json").write_text(settings, encoding="utf-8")

    if "copilot" in extras:
        inst.copy_tree(ROOT / "adapters" / "copilot" / ".github", ".github")
    if opts.workflows:
        inst.copy_tree(ROOT / "templates" / "workflows", ".github/workflows")

    claude_md = target / "CLAUDE.md"
    note = ""
    if claude_md.is_file() and "@AGENTS.md" not in claude_md.read_text(encoding="utf-8"):
        note = (
            "\nNote: your existing CLAUDE.md does not import @AGENTS.md. Add that line so all tools share instructions."
        )

    verb = "Would write" if opts.dry_run else "Wrote"
    print(f"{verb} {len(inst.written)} file(s) in {target}:")
    for rel in inst.written:
        print(f"  + {rel}")
    if inst.skipped:
        print(f"Skipped {len(inst.skipped)} existing file(s) (use --force to overwrite):")
        for rel in inst.skipped:
            print(f"  = {rel}")
    print("\nNext: fill in AGENTS.md, set .fleet/test-command, and review the diff before committing." + note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
