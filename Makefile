ifeq ($(OS),Windows_NT)
PYTHON ?= python
else
PYTHON ?= python3
endif
PIPX ?= pipx
.DEFAULT_GOAL := help
.NOTPARALLEL:
.PHONY: help install install-dev validate test smoke-test coverage format lint security clean build publish run dry-run batch show-config version pipx-install pipx-uninstall watch pre-commit list-plugins plugin-docs gui gui-test check package dev

help: ## List development commands without installation
	@"$(PYTHON)" tools/make-support.py help

install: ## Install the CLI in the selected Python environment
	"$(PYTHON)" -m pip install -e .

install-dev: ## Install CLI and development dependencies
	"$(PYTHON)" -m pip install -e ".[dev]"

validate: ## Validate required project files and runtime imports
	"$(PYTHON)" -c "from pathlib import Path; paths=['pyproject.toml','requirements.txt','downloader.py','tubetracks_gui.py','tests']; missing=[p for p in paths if not Path(p).exists()]; assert not missing, missing; import yt_dlp, rich"

test: ## Run all offline tests
	"$(PYTHON)" -m pytest tests/ -v --tb=short

smoke-test: ## Run quick smoke tests
	"$(PYTHON)" -m pytest tests/test_smoke.py -v --tb=short

coverage: ## Run tests with HTML and terminal coverage
	"$(PYTHON)" -m pytest tests/ -v --cov --cov-report=term-missing --cov-report=html

format: ## Apply Ruff import sorting and formatting
	"$(PYTHON)" -m ruff check --select I --fix .
	"$(PYTHON)" -m ruff format .

lint: ## Check Ruff rules and formatting
	"$(PYTHON)" -m ruff check .
	"$(PYTHON)" -m ruff format --check .

security: ## Run Bandit and audit the selected environment
	"$(PYTHON)" -m bandit -r downloader.py tubetracks_gui.py plugins -ll
	"$(PYTHON)" -m pip_audit --local --progress-spinner off

clean: ## Remove owned build/test outputs; preserve downloads and environments
	"$(PYTHON)" tools/make-support.py clean

build: validate ## Build wheel and source distribution
	"$(PYTHON)" -m build

publish: build ## Explicitly publish built archives to PyPI (requires credentials)
	"$(PYTHON)" -m twine upload dist/* --skip-existing

run: ## Download media; URL is required
	@"$(PYTHON)" -c "import sys; value=sys.argv[1]; sys.exit(0 if value.strip() else 'URL is required')" "$(URL)"
	"$(PYTHON)" downloader.py $(ARGS) "$(URL)"

dry-run: ## Preview media processing; URL is required
	@"$(PYTHON)" -c "import sys; value=sys.argv[1]; sys.exit(0 if value.strip() else 'URL is required')" "$(URL)"
	"$(PYTHON)" downloader.py --dry-run "$(URL)"

batch: ## Download the URLs in FILE
	@"$(PYTHON)" -c "import sys; value=sys.argv[1]; sys.exit(0 if value.strip() else 'FILE is required')" "$(FILE)"
	"$(PYTHON)" downloader.py -b "$(FILE)" $(ARGS)

show-config: ## Display current configuration
	"$(PYTHON)" downloader.py --show-config

version: ## Display the installed application version
	"$(PYTHON)" downloader.py --version

pipx-install: ## Explicitly install into a pipx environment
	"$(PIPX)" install .

pipx-uninstall: ## Explicitly remove the pipx installation
	"$(PIPX)" uninstall tubetracks

watch: ## Watch tests; requires pytest-watch in the selected environment
	"$(PYTHON)" -m pytest_watch

pre-commit: ## Install pre-commit and its repository hooks explicitly
	"$(PYTHON)" -m pip install pre-commit
	"$(PYTHON)" -m pre_commit install

list-plugins: ## List supported platform plugins
	"$(PYTHON)" downloader.py --list-plugins

plugin-docs: ## Display the plugin API documentation location and supported plugins
	@"$(PYTHON)" -c "from pathlib import Path; p=Path('PLUGIN_API.md'); assert p.is_file(); print(p.resolve())"
	"$(PYTHON)" downloader.py --list-plugins

gui: ## Launch the desktop GUI explicitly
	"$(PYTHON)" tubetracks_gui.py

gui-test: ## Check GUI imports without starting a window
	"$(PYTHON)" -c "import tkinter; import tubetracks_gui; print('GUI imports passed')"

check: lint test security ## Run all quality and security gates in order

package: build ## Build local wheel and source archives
	"$(PYTHON)" -m twine check dist/*

dev: watch ## Watch tests during development
