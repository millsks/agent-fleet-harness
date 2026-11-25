# AGENTS.md

Instructions for coding agents working on **agent-fleet-harness** itself. Keep this file short: it loads on every run, and some tools only read the first 16 KiB.

## What this repo is

A reusable harness for a fleet of SDLC coding agents. Claude Code formats are canonical; Copilot gets generated adapters; Devin reads the Claude Code layout directly. `scripts/install.py` copies the harness into other repos.

## Layout

- `.claude/agents/`: canonical agent definitions (source of truth)
- `.claude/skills/`: skills in the open Agent Skills format
- `.claude/settings.json`: Claude Code hooks, all calling `gates/`
- `gates/`: tool-neutral gate scripts. Python 3.9+, standard library only
- `adapters/copilot/`: generated from `.claude/agents/`; never edit by hand
- `templates/`: files `install.py` copies into target repos (AGENTS.md, `.fleet/`, workflows)
- `evals/`: replayable tasks for testing harness changes
- `scripts/`: `install.py`, `sync_adapters.py`, `validate.py`
- `docs/primer/`: the interactive primer (single HTML file)

## Commands

- `make check`: everything CI runs (lint, tests, validation, adapter sync check)
- `make test-fast`: unit tests only; the Stop gate runs this
- `make sync`: regenerate `adapters/copilot/` after changing `.claude/agents/`
- `make fmt`: format Python with ruff

## Rules

- Gates and scripts use only the Python standard library and must run on Python 3.9. Work sandboxes have no network and no extra packages.
- Never hardcode internal hostnames, credentials or employer-specific details. This repo is a public pattern library.
- After editing `.claude/agents/`, run `make sync` and commit the regenerated adapters.
- Every gate change needs a test in `tests/test_gates.py` covering both the Claude and Copilot payload formats.
- Work on a feature branch and open a PR. Do not call work done until `make check` and CI pass.
