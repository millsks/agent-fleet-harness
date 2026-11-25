# GitHub Copilot adapter

Everything under `.github/` here is **generated** from the canonical Claude Code files by `scripts/sync_adapters.py`. Do not edit it by hand: change `.claude/agents/` and run `make sync`. CI fails if the two drift apart.

`scripts/install.py <repo> --with copilot` copies these files into a target repository.

## What gets generated

| File | From | Notes |
|---|---|---|
| `.github/agents/<name>.agent.md` | `.claude/agents/<name>.md` | Keeps `name`, `description` and the prompt. Tools are mapped to Copilot aliases (`read`, `edit`, `search`, `execute`, `agent`, `web`). Claude-only fields (`model`, `maxTurns`, `isolation`, `memory`, `skills`) are dropped. |
| `.github/hooks/agent-fleet.json` | `gates/` | `preToolUse` hooks that run the same gate scripts with `--format copilot`, so the gates answer with `permissionDecision` JSON. |

## What Copilot does not get

- **The Stop gate.** Copilot has no hook that can refuse to finish, so "tests must pass" is enforced by CI and branch protection instead.
- **Turn budgets and worktree isolation.** Set limits in the Copilot cloud agent settings and rely on one branch per task.
- **Skills preloaded per agent.** Skills in `.claude/skills/` follow the open Agent Skills format; check which skill directories your Copilot version scans and symlink `.github/skills` to `.claude/skills` if needed.

Tool aliases and hook fields follow GitHub's custom agents configuration and hooks reference. Check them against the Copilot version your organisation runs.
