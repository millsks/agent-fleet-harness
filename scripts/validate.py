#!/usr/bin/env python3
"""Validate the harness: agents, skills, hook settings, instructions and workflows.

Claude Code silently ignores unknown frontmatter fields, so a typo such as
``maxturns`` fails quietly at runtime. This script makes it fail loudly in CI.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _frontmatter  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

AGENT_KEYS = {
    "name",
    "description",
    "tools",
    "disallowedTools",
    "model",
    "permissionMode",
    "isolation",
    "maxTurns",
    "autoCompactWindow",
    "skills",
    "mcpServers",
    "hooks",
    "memory",
    "background",
    "omitClaudeMd",
    "effort",
    "initialPrompt",
    "color",
}
KNOWN_TOOLS = {
    "Read",
    "Write",
    "Edit",
    "MultiEdit",
    "Grep",
    "Glob",
    "Bash",
    "Agent",
    "Task",
    "WebFetch",
    "WebSearch",
    "TodoWrite",
    "NotebookRead",
    "NotebookEdit",
}
MODELS = {"inherit", "opus", "sonnet", "haiku", "fable"}
PERMISSION_MODES = {"default", "manual", "acceptEdits", "auto", "dontAsk", "bypassPermissions", "plan"}
SKILL_KEYS = {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
AGENTS_MD_LIMIT = 16 * 1024
SKILL_BODY_LINE_LIMIT = 500


class Report:
    def __init__(self) -> None:
        self.errors: list[str] = []
        self.checked = 0

    def error(self, where: Path | str, message: str) -> None:
        where = where.relative_to(ROOT).as_posix() if isinstance(where, Path) else where
        self.errors.append(f"{where}: {message}")


def check_agents(report: Report, skills: set[str]) -> None:
    for path in sorted((ROOT / ".claude" / "agents").glob("*.md")):
        report.checked += 1
        try:
            doc = _frontmatter.load(path)
        except _frontmatter.FrontmatterError as exc:
            report.error(path, str(exc))
            continue
        meta = doc.meta
        for key in ("name", "description"):
            if not meta.get(key):
                report.error(path, f"missing required field '{key}'")
        if meta.get("name") and meta["name"] != path.stem:
            report.error(path, f"name '{meta['name']}' does not match file name '{path.stem}'")
        for key in set(meta) - AGENT_KEYS:
            report.error(path, f"unknown field '{key}' (Claude Code would silently ignore it)")
        for key in ("tools", "disallowedTools"):
            for tool in meta.get(key) or []:
                if tool not in KNOWN_TOOLS and not str(tool).startswith("mcp__"):
                    report.error(path, f"unknown tool '{tool}' in {key}")
        model = meta.get("model")
        if model and model not in MODELS and not str(model).startswith("claude-"):
            report.error(path, f"unknown model '{model}'")
        mode = meta.get("permissionMode")
        if mode and mode not in PERMISSION_MODES:
            report.error(path, f"unknown permissionMode '{mode}'")
        if meta.get("isolation") not in (None, "worktree"):
            report.error(path, "isolation must be 'worktree'")
        if "maxTurns" not in meta:
            report.error(path, "set maxTurns: every agent needs a turn budget")
        for skill in meta.get("skills") or []:
            if skill not in skills:
                report.error(path, f"references unknown skill '{skill}'")
        if len(doc.body.strip()) < 40:
            report.error(path, "prompt body is empty or too short")


def check_skills(report: Report) -> set[str]:
    names = set()
    for skill_dir in sorted(p for p in (ROOT / ".claude" / "skills").iterdir() if p.is_dir()):
        report.checked += 1
        path = skill_dir / "SKILL.md"
        if not path.is_file():
            report.error(skill_dir, "missing SKILL.md")
            continue
        try:
            doc = _frontmatter.load(path)
        except _frontmatter.FrontmatterError as exc:
            report.error(path, str(exc))
            continue
        name = str(doc.meta.get("name", ""))
        names.add(name)
        if name != skill_dir.name:
            report.error(path, f"name '{name}' must match directory '{skill_dir.name}'")
        if not NAME_RE.match(name) or len(name) > 64:
            report.error(path, "name must be lowercase letters, digits and hyphens, at most 64 characters")
        description = str(doc.meta.get("description", ""))
        if not description:
            report.error(path, "missing description")
        elif len(description) > 1024:
            report.error(path, "description longer than 1024 characters")
        for key in set(doc.meta) - SKILL_KEYS:
            report.error(path, f"field '{key}' is not in the Agent Skills spec")
        if len(doc.body.splitlines()) > SKILL_BODY_LINE_LIMIT:
            report.error(path, f"body over {SKILL_BODY_LINE_LIMIT} lines; move detail into reference files")
    return names


def check_settings(report: Report) -> None:
    path = ROOT / ".claude" / "settings.json"
    report.checked += 1
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        report.error(path, f"invalid JSON: {exc}")
        return
    for event, groups in settings.get("hooks", {}).items():
        for group in groups:
            for hook in group.get("hooks", []):
                for script in re.findall(r"gates/([\w.-]+\.py)", hook.get("command", "")):
                    if not (ROOT / "gates" / script).is_file():
                        report.error(path, f"{event} hook calls missing gates/{script}")


def check_instructions(report: Report) -> None:
    for path in (ROOT / "AGENTS.md", ROOT / "templates" / "AGENTS.md"):
        report.checked += 1
        if not path.is_file():
            report.error(path, "missing")
            continue
        size = path.stat().st_size
        if size > AGENTS_MD_LIMIT:
            report.error(path, f"{size} bytes; keep under {AGENTS_MD_LIMIT} (Devin reads only the first 16 KiB)")
    claude_md = ROOT / "CLAUDE.md"
    if "@AGENTS.md" not in claude_md.read_text(encoding="utf-8"):
        report.error(claude_md, "should import @AGENTS.md so every tool shares one set of instructions")


def check_workflows(report: Report) -> None:
    for path in sorted((ROOT / "templates" / "workflows").glob("*.yml")):
        report.checked += 1
        text = path.read_text(encoding="utf-8")
        if "\t" in text:
            report.error(path, "contains tab characters")
        if "timeout-minutes:" not in text:
            report.error(path, "every agent job needs timeout-minutes")
        if "anthropics/claude-code-action" in text and "--max-turns" not in text:
            report.error(path, "agent steps need --max-turns in claude_args")
        if "concurrency:" not in text:
            report.error(path, "add a concurrency group so agent runs cannot pile up")


def main() -> int:
    report = Report()
    skills = check_skills(report)
    check_agents(report, skills)
    check_settings(report)
    check_instructions(report)
    check_workflows(report)
    if report.errors:
        print("\n".join(report.errors))
        print(f"\n{len(report.errors)} problem(s) found.")
        return 1
    print(f"Harness valid: {report.checked} items checked.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
