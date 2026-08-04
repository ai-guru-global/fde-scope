.PHONY: install install-dev test run clean lint help

PYTHON ?= python3
PIP ?= pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install package (core data layer only)
	$(PIP) install -e .

install-dev: ## Install with dev + test deps
	$(PIP) install -e ".[dev]"

install-full: ## Install everything including agentscope + mysql extras
	$(PIP) install -e ".[dev,agentscope,mysql]"

test: ## Run the test suite (core layer needs no agentscope)
	$(PYTHON) -m pytest

test-cov: ## Run tests with coverage
	$(PYTHON) -m pytest --cov=fde_scope --cov-report=term-missing

run: ## Print CLI help (entrypoint)
	$(PYTHON) -m fde_scope.cli --help

clean: ## Remove build/test artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
