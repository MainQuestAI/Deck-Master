# Convenience wrappers for the rebuilt core; install development dependencies first.
PY ?= python
VENV ?= .venv
VENV_PY := $(VENV)/bin/python
ifneq ($(wildcard $(VENV_PY)),)
  PY := $(VENV_PY)
endif
RUN = $(PY) -m deck_master
OUT ?= dist/release
REGISTRY ?= ./deck-master-projects.json

.PHONY: help install-dev browser-deps test smoke package preview release-build release-smoke rc-gate rc-gate-ci
help: ## Show supported targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-18s %s\n", $$1, $$2}'

install-dev: ## Create .venv and install development dependencies
	$(PY) -m venv $(VENV)
	$(VENV_PY) -m pip install -e ".[dev]"

browser-deps: ## Install Playwright Chromium and its system dependencies
	$(PY) -m playwright install --with-deps chromium

test: ## Run core unit tests; renderer and browser gates are separate in CI
	$(PY) tools/run_heavy_tests.py --record dist/test-evidence/local-unit.json -- $(PY) -m pytest -q tests/rebuild -m "not render and not browser"

smoke: ## Inspect the installed CLI and package boundaries (no model or approval)
	$(RUN) --help
	$(RUN) capabilities
	$(PY) -m pytest -q tests/rebuild/test_package_boundary.py tests/rebuild/test_entry_capabilities.py

package: ## Build wheel, sdist and provenance into a NEW OUT directory
	$(PY) tools/build_release.py --out "$(OUT)"

preview: ## Open the current local Workbench launcher; preserves the chosen registry
	$(RUN) workbench --registry "$(REGISTRY)" --no-open

release-build release-smoke rc-gate rc-gate-ci:
	@echo 'Retired target. Use make package for artifacts and .github/workflows/rebuild.yml: unit matrix, render, required browser and installed/offline checks.' >&2
	@exit 2
