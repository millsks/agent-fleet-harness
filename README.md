# agent-fleet-harness

Reusable harness for a fleet of SDLC coding agents: agent definitions, skills, hooks, quality gates, CI workflows and evals. Claude Code first, with Copilot and Devin support.

An agent is the model plus its harness: the instructions, context, tools, permissions, checks and feedback around it. This repo is that harness, packaged so you can install it into any repository and improve it in one place.

## The fleet

Each station is a narrow agent with its own tools, a turn budget, and a gate before work moves on.

| Station | Agent | Trigger | Hands off | Gate |
|---|---|---|---|---|
| Triage | `triager` | Issue opened | Labels, `agent:plan` or `needs-human` | Structured verdict; unclear issues go to a human |
| Plan | `planner` | `agent:plan` label | `specs/<issue>.md` | **Human** approves the spec with `agent:build` |
| Build | `implementer` | `agent:build` label | Draft PR from a worktree | Stop gate: checks must pass before it can finish |
| Test | `test-writer` | Called by the implementer | Tests mapped to acceptance criteria | Written from the spec, never from the code |
| Review | `reviewer` | PR opened or updated | PR review, `BLOCKING` or `NIT` | Read-only; **human** merges |
| Release | `releaser` | When preparing a release | Changelog and version bump | **Human** tags and publishes |
| Operate | `watcher` | Nightly | De-duplicated issues for failures and flakes | At most five issues per run |
| Heal | `healer` | CI failed on a feature branch | `[agent-heal]` fix or `heal-report.md` | Three attempts a day, stops on repeated errors |
| Learn | `retro` | Weekly | Harness change proposals as a PR | Evidence from two or more incidents; evals; **human** merges |

## Tool support

Claude Code formats are canonical. Other tools either read them directly or get generated adapters.

| | Claude Code | Devin | GitHub Copilot |
|---|---|---|---|
| Instructions | `AGENTS.md` via `CLAUDE.md` | Reads `AGENTS.md` | Reads `AGENTS.md` |
| Skills | `.claude/skills/` | Scans `.claude/skills/` | Check your version's skill paths |
| Agents | `.claude/agents/` | Devin CLI imports `.claude/` | Generated `.github/agents/*.agent.md` |
| Pre-tool gates | `.claude/settings.json` | Claude Code compatible hooks | Generated `.github/hooks/agent-fleet.json` |
| Stop gate | Yes | Via Claude Code hooks | No: enforced in CI |

Gates are plain Python 3.9+ with no dependencies, so they run in sandboxed environments with no network access.

## Quick start

Install into another repository:

```bash
git clone https://github.com/millsks/agent-fleet-harness
python3 agent-fleet-harness/scripts/install.py ../my-service
```

Options:

```bash
--with copilot   # also add Copilot agents and hooks under .github/
--workflows      # also add GitHub Actions workflow templates
--models inherit # where model aliases are not allowed, use the session's model
--dry-run        # show what would change
--force          # overwrite existing files (settings.json hooks are always merged)
```

Then in the target repo:

1. Fill in `AGENTS.md`: setup, commands, map and rules for that codebase.
2. Set the fast check command in `.fleet/test-command` (under two minutes).
3. Review `.fleet/protected-paths` and `.fleet/blocked-commands`.
4. If you added workflows, set the `ANTHROPIC_API_KEY` secret and, for the healer, a GitHub App token as `HEALER_APP_TOKEN`.
5. Commit on a branch and open a PR.

Installed files land in `.claude/`, `.fleet/` (gates and config), `evals/`, and optionally `.github/`. Existing files are never overwritten without `--force`.

## Gates

| Gate | Event | Blocks |
|---|---|---|
| `protect_paths.py` | Before Edit or Write | Paths matched by `.fleet/protected-paths` (defaults: `.git/`, `.env*`, `secrets/`, workflows, `.fleet/` itself) |
| `guard_commands.py` | Before a shell command | Force pushes, pushes to `main`, deleting tags or remote branches, `--no-verify`, history rewrites, `curl … \| sh`, plus regexes in `.fleet/blocked-commands` |
| `require_green.py` | When the agent tries to stop | Finishing while the command in `.fleet/test-command` fails; the failure output goes back to the agent |

Each gate reads Claude Code payloads by default and Copilot payloads with `--format copilot`. The Stop gate skips when nothing changed and always lets go on the second attempt to avoid loops.

## Workflows

Templates in `templates/workflows/`, built on [`anthropics/claude-code-action@v1`](https://github.com/anthropics/claude-code-action). Every job has a timeout, a concurrency group and a `--max-turns` budget; `scripts/validate.py` enforces that.

| Workflow | Runs |
|---|---|
| `agent-triage.yml` | On new issues |
| `agent-build.yml` | On `agent:plan` and `agent:build` labels |
| `agent-review.yml` | On pull requests |
| `agent-heal.yml` | When the `CI` workflow fails on a feature branch |
| `agent-watch.yml` | Nightly |
| `agent-retro.yml` | Weekly |

## Evals

`evals/run.sh` replays past tasks against the current harness in fresh worktrees and records pass rate, cost and turns. Run it before merging any change to agents, skills, hooks or `AGENTS.md`. See [`evals/README.md`](evals/README.md).

## Layout

```
AGENTS.md                instructions for agents working on this repo
.claude/agents/          canonical agent definitions
.claude/skills/          write-spec, fix-ci-failure, tighten-harness
.claude/settings.json    hooks calling gates/
gates/                   tool-neutral gate scripts
adapters/copilot/        generated Copilot agents and hooks
templates/               AGENTS.md, .fleet/ config and workflows for target repos
evals/                   replayable tasks and runner
scripts/                 install.py, sync_adapters.py, validate.py
docs/primer/index.html   interactive primer on building an agent fleet
```

## Learn the ideas

Open [`docs/primer/index.html`](docs/primer/index.html) in a browser for an interactive primer: harness engineering, the agent loop and its failure modes, context and tool design, gates, self-healing, self-learning, and evaluation.

## Development

```bash
make check      # lint, tests, validation, adapter sync check (what CI runs)
make test-fast  # unit tests; the Stop gate runs this
make sync       # regenerate adapters/copilot after editing .claude/agents
make fmt        # format with ruff
```

Linting needs `ruff` and `shellcheck` (`pip install ruff shellcheck-py`). Everything else uses the Python standard library.

## License

[MIT](LICENSE)
