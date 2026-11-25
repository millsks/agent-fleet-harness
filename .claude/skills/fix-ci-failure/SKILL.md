---
name: fix-ci-failure
description: Diagnose a failed CI run, classify it, and fix only code or lint failures with hard stop rules. Use when a CI run on a feature branch has failed.
---

# Fix a CI failure

## 1. Get the log
If `ci-failure.log` exists, read it. Otherwise run `gh run view <run-id> --log-failed | tail -n 400`.

## 2. Find the first failure
Later failures are often caused by the first one. Find the first failing step and the first error inside it.

## 3. Classify it

| Class | Signs | Action |
|---|---|---|
| CODE | Assertion or exception in project code | Fix the root cause |
| LINT | Formatter, linter or type checker error | Fix it; run the same tool locally |
| FLAKY | Timing, ordering or network-dependent test; passes on rerun | No code change. Report it for quarantine |
| INFRA | Registry, runner, network or credential failure outside the repo | No code change. Report it |
| UNKNOWN | You cannot explain it with evidence | No code change. Write up what you found |

## 4. Check the breakers
Stop and report instead of fixing if any is true:
- three or more commits starting with `[agent-heal]` on this branch in the last 24 hours
- the same error signature as the last `[agent-heal]` attempt
- the fix would require editing tests' assertions, CI config, or `.fleet/`

## 5. Fix and verify
Make the smallest change that fixes the root cause. Run the fast checks. Commit with a message starting `[agent-heal] fix:`.

## 6. Report
Write `heal-report.md`:

```
Class: CODE | LINT | FLAKY | INFRA | UNKNOWN
First failure: <step> / <test or file:line>
Root cause: <one or two sentences>
Change: <what you changed, or "none" and why>
Verified with: <commands and results>
```
