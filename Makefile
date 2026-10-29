.PHONY: install install-dev install-full test test-cov lint run clean help check-catalog check-local build-site fetch-resources check-resources build-resources-site

# Use the project venv when it exists. A bare `python3` on macOS resolves to
# Homebrew's interpreter, which has none of the deps: `make test` died at
# collection with ModuleNotFoundError, and `make install*` pip-installed into
# the system Python. Override per-call: `make test PYTHON=python3.12`.
VENV_PY := $(wildcard .venv/bin/python)
PYTHON ?= $(if $(VENV_PY),$(VENV_PY),python3)
PIP ?= $(PYTHON) -m pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Install package (core data layer only)
	$(PIP) install -e .

install-dev: ## Install with dev + test deps
	$(PIP) install -e ".[dev]"

install-full: ## Install everything (dev + agentscope + mysql + opcua + mqtt + ros2 + web)
	$(PIP) install -e ".[full]"

test: ## Run the test suite (core layer needs no agentscope)
	$(PYTHON) -m pytest

test-cov: ## Run tests with coverage
	$(PYTHON) -m pytest --cov=fde_scope --cov-report=term-missing

lint: ## Ruff + mypy (tools are not in .[dev]; install them separately)
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .
	$(PYTHON) -m mypy fde_scope

check-catalog: ## Validate docs/skills-catalog (counts, sections, index, links)
	$(PYTHON) scripts/check_skills_catalog.py

check-local: ## Also reconcile catalog ✅/📦 status against ~/.qoder installs
	$(PYTHON) scripts/check_skills_catalog.py --local

build-site: ## Rebuild docs/skills-catalog/site/index.html portal (run after editing catalog)
	$(PYTHON) scripts/build_catalog_site.py

# GitHub FDE resources (docs/github-resources/). fetch hits the network via `gh`
# (OFFLINE=1 replays manifest/snapshot without touching the network, for CI);
# check reconciles README ⇄ manifest ⇄ disk ⇄ NOTICE; build renders the portal.
fetch-resources: ## Harvest FDE GitHub repos → manifest + verbatim mirror (OFFLINE=1 for no-network)
	$(PYTHON) scripts/fetch_github_resources.py $(if $(OFFLINE),--offline,)

check-resources: ## Validate docs/github-resources (counts, mirror⇔manifest, provenance, NOTICE)
	$(PYTHON) scripts/check_resources_catalog.py

build-resources-site: ## Rebuild docs/github-resources/site/ portal (zh + en) from the manifest
	$(PYTHON) scripts/build_resources_site.py

run: ## Print CLI help (entrypoint)
	$(PYTHON) -m fde_scope.cli --help

clean: ## Remove build/test artifacts
	rm -rf build dist *.egg-info .pytest_cache .coverage htmlcov
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	find . -type d -name .ruff_cache -prune -exec rm -rf {} +
