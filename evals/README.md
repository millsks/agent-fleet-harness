# Evals

A fixed set of past tasks to replay whenever the harness changes (AGENTS.md, agents, skills, hooks). If the pass rate drops or cost jumps, the change made things worse.

## Add a task

1. Pick a real issue your team already solved.
2. Create `evals/tasks/<id>/`:
   - `base_commit`: the commit just before the fix
   - `prompt.md`: the issue text as an agent would get it
   - `check.sh`: the tests from the real fix; exit 0 on pass. The agent never sees this file.
3. Run `evals/run.sh <id>` once to confirm the task is solvable.

Start with 20 to 30 tasks across bug fixes, small features and refactors.

## Run

```bash
evals/run.sh              # all tasks
evals/run.sh fix-slugify  # one task
```

Results go to `evals/results/<timestamp>-<sha>/` (gitignored): one JSON transcript per task plus `summary.txt`. Runs vary, so compare the average of two or three runs before accepting a harness change.

The `example` task is a template and is skipped until you set its `base_commit`.
