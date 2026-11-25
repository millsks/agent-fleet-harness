---
name: tighten-harness
description: Turn a repeated agent mistake into the most deterministic harness fix (test, lint rule, hook, skill or instruction). Use when an agent slips, in retrospectives, or when proposing harness changes.
---

# Tighten the harness

When an agent gets something wrong, fix the harness so it cannot happen again, not just this once.

## Pick the strongest fix that works

Prefer earlier options. Move down only when an earlier one cannot express the rule.

1. **Test or check**: a test, lint rule or CI check that fails when the mistake happens. Its error message should say how to fix it.
2. **Hook**: a gate in `gates/` (or a pattern in `.fleet/protected-paths` or `.fleet/blocked-commands`) that blocks the action at runtime.
3. **Tool or scaffold**: a script, generator or MCP tool that makes the right way the easy way.
4. **Skill**: a procedure in `.claude/skills/` for multi-step work that keeps going wrong.
5. **Instruction**: one line in AGENTS.md or an agent prompt. Last resort; prose can be ignored.

## Every proposal includes

- **Evidence**: at least two incidents (PR or run links).
- **The change**: the exact diff or file to add.
- **The eval case**: the past task to add to `evals/tasks/` so a regression is caught.
- **What it replaces**: any older rule this makes redundant, to delete.

## Keep it short

AGENTS.md is read by every agent on every run, and some tools truncate it (Devin reads the first 16 KiB). Adding a line there has a cost. Delete rules that nothing has needed for 30 days.
