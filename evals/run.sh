#!/usr/bin/env bash
# Replay a fixed set of past tasks against the current harness and record pass/fail and cost.
#
# Each task directory under evals/tasks/ contains:
#   base_commit   commit to start from (one line)
#   prompt.md     the task, as an agent would receive it
#   check.sh      exits 0 if the task was done correctly (hidden tests, not shown to the agent)
#
# Usage: evals/run.sh [task-name ...]    (default: all tasks)
# Env:   EVAL_MAX_TURNS (default 30), EVAL_AGENT_CMD (default "claude")
set -euo pipefail

root=$(git rev-parse --show-toplevel)
cd "$root"
max_turns=${EVAL_MAX_TURNS:-30}
agent_cmd=${EVAL_AGENT_CMD:-claude}
out="evals/results/$(date +%Y%m%d-%H%M%S)-$(git rev-parse --short HEAD)"
mkdir -p "$out"

if [ "$#" -gt 0 ]; then
  tasks=("$@")
else
  tasks=()
  for dir in evals/tasks/*/; do
    tasks+=("$(basename "$dir")")
  done
fi

pass=0
total=0
for id in "${tasks[@]}"; do
  task="$root/evals/tasks/$id"
  if [ ! -f "$task/base_commit" ] || [ "$(tr -d '[:space:]' < "$task/base_commit")" = "REPLACE_ME" ]; then
    echo "$id skip (no base_commit)" | tee -a "$out/summary.txt"
    continue
  fi
  total=$((total + 1))
  wt=$(mktemp -d)
  git worktree add --quiet --detach "$wt" "$(tr -d '[:space:]' < "$task/base_commit")"
  # Evaluate the harness under test, not the one at the task's base commit.
  for item in .claude .fleet AGENTS.md CLAUDE.md; do
    if [ -e "$item" ]; then
      rm -rf "${wt:?}/$item"
      cp -R "$item" "$wt/"
    fi
  done

  (cd "$wt" && "$agent_cmd" -p "$(cat "$task/prompt.md")" --max-turns "$max_turns" \
      --output-format json > "$root/$out/$id.json") || true

  if (cd "$wt" && bash "$task/check.sh" > "$root/$out/$id.check.log" 2>&1); then
    result=pass
    pass=$((pass + 1))
  else
    result=fail
  fi
  cost=$(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print(d.get("total_cost_usd","n/a"), d.get("num_turns","n/a"))' "$out/$id.json" 2>/dev/null || echo "n/a n/a")
  echo "$id $result cost_usd/turns=$cost" | tee -a "$out/summary.txt"
  git worktree remove --force "$wt"
done

echo "passed $pass of $total" | tee -a "$out/summary.txt"
echo "results in $out"
