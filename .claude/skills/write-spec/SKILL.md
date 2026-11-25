---
name: write-spec
description: Write a spec for an issue before any code changes, with files in scope, acceptance criteria and a test plan. Use when planning a feature or bug fix.
---

# Write a spec

Copy `template.md` (next to this file) to `specs/<issue-number>.md` and fill every section.

## Rules

- **Read before you name.** Every file, function and command in the spec must exist; check with Grep or Glob.
- **Files in scope is a contract.** The implementer may only change these files. Keep the list short. If a change needs more than about eight files, split the issue.
- **Acceptance criteria are observable.** "Returns 404 when the order does not exist" is testable. "Handles missing orders properly" is not.
- **Bugs need a reproduction.** Give the exact input and the wrong output, and name the test that will fail before the fix.
- **Root cause, not symptom.** For bugs, state why it happens. A fix that hides the symptom will be rejected in review.
- **Open questions stop the line.** Anything that needs a human decision goes under Open questions, and the issue is not ready for building until they are answered.
