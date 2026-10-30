# Everything CI runs, a developer can run with one command (§3.11).
# CI calls these same targets, so local and CI behaviour cannot drift.
.DEFAULT_GOAL := help
.PHONY: help install format format-black lint typecheck test test-integration check clean

PYTHON ?= python3
SRC := src tests

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Create the dev environment and install pre-commit hooks
	$(PYTHON) -m pip install -e ".[dev]"
	pre-commit install

format:  ## Format with ruff format, then apply safe lint fixes
	ruff format .
	ruff check --fix .

format-black:  ## Format with Black instead of ruff format
	black .
	ruff check --fix .

lint:  ## Lint (no fixes)
	ruff check .

typecheck:  ## Static type check
	mypy src tests

test:  ## Run the test suite with coverage
	pytest

test-integration:  ## Run only the integration tests
	pytest -m integration --no-cov

check: lint typecheck test  ## Everything CI runs. Run this before opening a PR.
	ruff format --check .

clean:  ## Remove caches and build artefacts
	rm -rf .pytest_cache .ruff_cache .mypy_cache .coverage htmlcov dist build
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
