# Deck Master Makefile. Convenience wrappers so contributors do not have to
# memorize the long CLI invocations. Uses the project venv if present.

PY ?= python
SCRIPT ?= scripts/deck_master.py
VENV ?= .venv
VENV_PY := $(VENV)/bin/python

# Use the venv interpreter when it exists, else fall back to PY.
ifeq ($(shell test -x $(VENV_PY) && echo yes),yes)
  RUN := $(VENV_PY) $(SCRIPT)
  PY := $(VENV_PY)
else
  RUN := $(PY) $(SCRIPT)
endif

.PHONY: help install-dev test smoke release-smoke rc-gate rc-gate-ci preview browser-deps clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install-dev: ## Create .venv (Python 3.12) and install dev dependencies
	python3.12 -m venv $(VENV) || python3 -m venv $(VENV)
	$(VENV_PY) -m pip install --upgrade pip
	$(VENV_PY) -m pip install -e ".[dev]"

browser-deps: ## Install Playwright Chromium browsers
	$(PY) -m playwright install --with-deps chromium

test: ## Run the full unit test suite
	$(PY) -m unittest discover -s tests

smoke: ## Run the fixture autoplan + preview gate smoke
	$(RUN) autoplan \
		--brief-file examples/briefs/retail_digital_transformation.txt \
		--industry retail --library-mode fixture --run-mode fixture \
		--dev-allow-unsetup --run-id make-smoke
	$(RUN) preview-gate --run-dir runs/make-smoke --expect-unconfigured-backend-ok

release-smoke: ## Build and smoke a release tree
	$(RUN) release-build --output /tmp/deck-master-release --force
	$(RUN) release-smoke --release-root /tmp/deck-master-release

rc-gate: ## Run the FULL rc-gate (needs local-only benchmark + bound backend)
	$(RUN) rc-gate --require-browser-smoke --force

rc-gate-ci: ## Run the CI-tier rc-gate (reproducible on a fresh clone)
	$(RUN) rc-gate --tier ci --skip-browser-smoke --force

preview: ## Start the Review Desk on the fixture demo (http://127.0.0.1:5050)
	$(PY) scripts/preview/server.py examples/preview-run --port 5050

clean: ## Remove transient run/report artifacts
	rm -rf runs/make-smoke /tmp/deck-master-release
