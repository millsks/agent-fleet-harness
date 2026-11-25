"""Tests for the frontmatter parser, validator, adapter sync and installer."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import _frontmatter  # noqa: E402
import sync_adapters  # noqa: E402


def run_script(name: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], capture_output=True, text=True)


class FrontmatterTest(unittest.TestCase):
    def test_parses_scalars_lists_and_comments(self):
        doc = _frontmatter.parse(
            "---\nname: x\n# note\ntools: Read, Grep\nmaxTurns: 10\nbackground: true\n---\n\nBody\n"
        )
        self.assertEqual(doc.meta["name"], "x")
        self.assertEqual(doc.meta["tools"], ["Read", "Grep"])
        self.assertEqual(doc.meta["maxTurns"], 10)
        self.assertIs(doc.meta["background"], True)
        self.assertEqual(doc.body, "Body\n")

    def test_inline_list(self):
        doc = _frontmatter.parse("---\ntools: ['read', 'edit']\n---\n")
        self.assertEqual(doc.meta["tools"], ["read", "edit"])

    def test_missing_delimiters(self):
        with self.assertRaises(_frontmatter.FrontmatterError):
            _frontmatter.parse("name: x\n")
        with self.assertRaises(_frontmatter.FrontmatterError):
            _frontmatter.parse("---\nname: x\n")

    def test_duplicate_key(self):
        with self.assertRaises(_frontmatter.FrontmatterError):
            _frontmatter.parse("---\nname: a\nname: b\n---\n")

    def test_round_trip(self):
        text = _frontmatter.dump({"name": "a", "tools": ["read", "edit"]}, "Body\n")
        doc = _frontmatter.parse(text)
        self.assertEqual(doc.meta, {"name": "a", "tools": ["read", "edit"]})


class ValidateTest(unittest.TestCase):
    def test_repository_is_valid(self):
        result = run_script("validate.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class SyncAdaptersTest(unittest.TestCase):
    def test_adapters_are_in_sync(self):
        result = run_script("sync_adapters.py", "--check")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_tool_mapping_respects_disallowed(self):
        tools = sync_adapters.copilot_tools(["Read", "Grep", "Glob", "Bash", "Edit"], ["Edit"])
        self.assertEqual(tools, ["read", "search", "execute"])

    def test_generated_agent_drops_claude_only_fields(self):
        rel, content = sync_adapters.render_agent(ROOT / ".claude" / "agents" / "implementer.md")
        self.assertEqual(rel, "agents/implementer.agent.md")
        doc = _frontmatter.parse(content)
        self.assertEqual(set(doc.meta), {"name", "description", "tools"})
        self.assertIn("Generated from .claude/agents/implementer.md", doc.body)

    def test_hooks_use_copilot_format(self):
        hooks = json.loads(sync_adapters.render_hooks())
        self.assertEqual(hooks["version"], 1)
        commands = [h["bash"] for h in hooks["hooks"]["preToolUse"]]
        self.assertTrue(all("--format copilot" in c and ".fleet/gates/" in c for c in commands))


class InstallTest(unittest.TestCase):
    def test_install_into_empty_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            result = run_script("install.py", str(target), "--with", "copilot", "--workflows", "--models", "inherit")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((target / ".fleet" / "gates" / "require_green.py").is_file())
            self.assertTrue((target / ".claude" / "skills" / "write-spec" / "SKILL.md").is_file())
            self.assertTrue((target / ".github" / "agents" / "reviewer.agent.md").is_file())
            self.assertTrue((target / ".github" / "hooks" / "agent-fleet.json").is_file())
            self.assertTrue((target / ".github" / "workflows" / "agent-heal.yml").is_file())
            agent = (target / ".claude" / "agents" / "reviewer.md").read_text()
            self.assertIn("model: inherit", agent)
            settings = json.loads((target / ".claude" / "settings.json").read_text())
            commands = [h["command"] for g in settings["hooks"]["Stop"] for h in g["hooks"]]
            self.assertTrue(any(".fleet/gates/require_green.py" in c for c in commands))

    def test_install_keeps_existing_files_and_merges_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            (target / "AGENTS.md").write_text("mine\n")
            (target / ".claude").mkdir()
            existing = {
                "permissions": {"allow": ["Bash(make *)"]},
                "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo hi"}]}]},
            }
            (target / ".claude" / "settings.json").write_text(json.dumps(existing))

            first = run_script("install.py", str(target))
            second = run_script("install.py", str(target))
            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual((target / "AGENTS.md").read_text(), "mine\n")
            settings = json.loads((target / ".claude" / "settings.json").read_text())
            self.assertEqual(settings["permissions"], existing["permissions"])
            stop_commands = [h["command"] for g in settings["hooks"]["Stop"] for h in g["hooks"]]
            self.assertEqual(len(stop_commands), 2, "re-running install must not duplicate hooks")
            self.assertIn("Skipped", second.stdout)

    def test_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_script("install.py", tmp, "--dry-run")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Would write", result.stdout)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_installed_gates_work_from_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            run_script("install.py", str(target))
            result = subprocess.run(
                [sys.executable, str(target / ".fleet" / "gates" / "protect_paths.py")],
                input=json.dumps({"tool_name": "Edit", "tool_input": {"file_path": ".fleet/gates/protect_paths.py"}}),
                capture_output=True,
                text=True,
                cwd=target,
                env={k: v for k, v in os.environ.items() if k != "CLAUDE_PROJECT_DIR"},
            )
            self.assertEqual(result.returncode, 2, "installed gates must protect themselves")


if __name__ == "__main__":
    unittest.main()
