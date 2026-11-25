PYTHON ?= python3

.PHONY: check lint fmt test test-fast validate sync sync-check

check: lint test validate sync-check ## Everything CI runs

lint: ## Lint Python and shell
	ruff check .
	ruff format --check .
	shellcheck evals/run.sh evals/tasks/*/check.sh

fmt: ## Format Python
	ruff format .
	ruff check --fix .

test: ## Full test suite
	$(PYTHON) -m unittest discover -s tests -v

test-fast: ## Quick unit tests (used by the Stop gate)
	$(PYTHON) -m unittest discover -s tests -q

validate: ## Validate agents, skills, settings and AGENTS.md
	$(PYTHON) scripts/validate.py

sync: ## Regenerate adapters from .claude/agents
	$(PYTHON) scripts/sync_adapters.py

sync-check: ## Fail if adapters are out of date
	$(PYTHON) scripts/sync_adapters.py --check
