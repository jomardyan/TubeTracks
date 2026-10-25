.PHONY: help install install-dev test smoke-test lint format clean build publish run dry-run show-config version pipx-install pipx-uninstall check coverage pre-commit security validate watch list-plugins plugin-docs batch gui gui-test

# Color codes for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# Default target
help:
	@echo "$(BLUE)╔════════════════════════════════════════════════════════════╗$(NC)"
	@echo "$(BLUE)║       TubeTracks - Make Commands                           ║$(NC)"
	@echo "$(BLUE)╚════════════════════════════════════════════════════════════╝$(NC)"
	@echo ""
	@echo "$(GREEN)Installation & Setup:$(NC)"
	@echo "  make install         Install package and dependencies"
	@echo "  make install-dev     Install with development tools"
	@echo "  make pipx-install    Install globally via pipx"
	@echo "  make pipx-uninstall  Uninstall global installation"
	@echo ""
	@echo "$(GREEN)Development & Quality:$(NC)"
	@echo "  make test            Run all tests"
	@echo "  make smoke-test      Run quick validation tests"
	@echo "  make coverage        Generate test coverage report"
	@echo "  make lint            Check code style"
	@echo "  make format          Auto-format code (Ruff)"
	@echo "  make security        Run security checks"
	@echo "  make check           Run lint, tests and security checks"
	@echo "  make validate        Validate project structure and dependencies"
	@echo ""
	@echo "$(GREEN)Build & Distribution:$(NC)"
	@echo "  make clean           Remove build artifacts and cache"
	@echo "  make build           Build distribution packages"
	@echo "  make publish         Publish to PyPI"
	@echo ""
	@echo "$(GREEN)Download Operations:$(NC)"
	@echo "  make run URL=<url>   Download from YouTube URL"
	@echo "  make dry-run URL=<url> Preview download without processing"
	@echo "  make batch FILE=<file> Download from batch file"
	@echo "  make gui             Launch desktop GUI application"
	@echo ""
	@echo "$(GREEN)Plugin System:$(NC)"
	@echo "  make list-plugins    List all supported platform plugins"
	@echo "  make plugin-docs     Show plugin API documentation"
	@echo ""
	@echo "$(GREEN)Information:$(NC)"
	@echo "  make show-config     Display current configuration"
	@echo "  make version         Show installed version"
	@echo "  make help            Show this help message"
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make run URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ'"
	@echo "  make run URL='https://www.youtube.com/watch?v=VIDEO_ID' ARGS='-q high -f flac'"
	@echo "  make batch FILE='urls.txt' ARGS='-q best -f flac'"
	@echo "  make dry-run URL='https://www.youtube.com/watch?v=VIDEO_ID'"
	@echo "  make run URL='https://www.tiktok.com/@creator/video/123456789'"
	@echo "  make run URL='https://soundcloud.com/artist/track'"
	@echo "  make gui                          # Launch desktop GUI"
	@echo ""

# Install the package
install:
	@echo "$(BLUE)→ Installing package...$(NC)"
	pip install -e .
	@echo "$(GREEN)✓ Installation complete$(NC)"

# Install with dev dependencies
install-dev:
	@echo "$(BLUE)→ Installing with development dependencies...$(NC)"
	pip install -e ".[dev]"
	@echo "$(GREEN)✓ Development setup complete$(NC)"

# Validate project structure and dependencies
validate:
	@echo "$(BLUE)→ Validating project structure...$(NC)"
	@test -f pyproject.toml || (echo "$(RED)✗ Missing pyproject.toml$(NC)" && exit 1)
	@test -f requirements.txt || (echo "$(RED)✗ Missing requirements.txt$(NC)" && exit 1)
	@test -f downloader.py || (echo "$(RED)✗ Missing downloader.py$(NC)" && exit 1)
	@test -f tubetracks_gui.py || (echo "$(RED)✗ Missing tubetracks_gui.py$(NC)" && exit 1)
	@test -d tests || (echo "$(RED)✗ Missing tests directory$(NC)" && exit 1)
	@echo "$(GREEN)✓ Project structure is valid$(NC)"
	@echo "$(BLUE)→ Checking dependencies...$(NC)"
	@python -c "import yt_dlp; import rich" 2>/dev/null || (echo "$(RED)✗ Missing required dependencies. Run: make install$(NC)" && exit 1)
	@echo "$(GREEN)✓ All dependencies installed$(NC)"

# Run tests
test:
	@echo "$(BLUE)→ Running all tests...$(NC)"
	python -m pytest tests/ -v --tb=short

# Run smoke tests only
smoke-test:
	@echo "$(BLUE)→ Running smoke tests...$(NC)"
	python -m pytest tests/test_smoke.py -v --tb=short

# Generate coverage report
coverage:
	@echo "$(BLUE)→ Generating coverage report...$(NC)"
	python -m pytest tests/ -v --cov --cov-report=term-missing --cov-report=html
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

# Format code and imports with the same tool used in CI
format:
	python -m ruff check --select I --fix .
	python -m ruff format .

# Quality checks must propagate failures
lint:
	python -m ruff check .
	python -m ruff format --check .

security:
	python -m bandit -r downloader.py tubetracks_gui.py plugins -ll
	python -m pip_audit --local --progress-spinner off

check: lint test security

# Clean build artifacts
clean:
	@echo "$(BLUE)→ Cleaning build artifacts...$(NC)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	rm -rf htmlcov/
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Build distribution
build: clean validate
	@echo "$(BLUE)→ Building distribution packages...$(NC)"
	python -m build
	@echo "$(GREEN)✓ Build complete - packages in dist/$(NC)"

# Publish to PyPI (requires twine and PyPI credentials)
publish: build
	@echo "$(YELLOW)⚠ Publishing to PyPI...$(NC)"
	@echo "$(YELLOW)Ensure you have:$(NC)"
	@echo "$(YELLOW)  1. Created PyPI account at https://pypi.org/account/register/$(NC)"
	@echo "$(YELLOW)  2. Generated API token at https://pypi.org/account/api-tokens/$(NC)"
	@echo "$(YELLOW)  3. Configured ~/.pypirc with your token (chmod 600 ~/.pypirc)$(NC)"
	@echo "$(YELLOW)$(NC)"
	@echo "$(YELLOW)See PyPI_PUBLISHING.md for detailed instructions.$(NC)"
	@echo "$(YELLOW)$(NC)"
	python -m twine upload dist/* --skip-existing
	@echo "$(GREEN)✓ Published to PyPI!$(NC)"
	@echo "$(GREEN)View at: https://pypi.org/project/tubetracks/$(NC)"

# Run the downloader
run:
ifndef URL
	@echo "$(RED)✗ Error: URL is required$(NC)"
	@echo "$(YELLOW)Usage: make run URL='https://www.youtube.com/watch?v=VIDEO_ID'$(NC)"
	@echo "$(YELLOW)Optional: make run URL='...' ARGS='-q high -f flac'$(NC)"
	@exit 1
endif
	@echo "$(BLUE)→ Starting download...$(NC)"
	python downloader.py $(ARGS) "$(URL)"

# Run with dry-run
dry-run:
ifndef URL
	@echo "$(RED)✗ Error: URL is required$(NC)"
	@echo "$(YELLOW)Usage: make dry-run URL='https://www.youtube.com/watch?v=VIDEO_ID'$(NC)"
	@exit 1
endif
	@echo "$(BLUE)→ Preview mode (no files will be downloaded)$(NC)"
	python downloader.py --dry-run "$(URL)"

# Batch download from file
batch:
ifndef FILE
	@echo "$(RED)✗ Error: FILE is required$(NC)"
	@echo "$(YELLOW)Usage: make batch FILE='urls.txt'$(NC)"
	@echo "$(YELLOW)Optional: make batch FILE='urls.txt' ARGS='-q high -f flac'$(NC)"
	@exit 1
endif
	@test -f "$(FILE)" || (echo "$(RED)✗ File not found: $(FILE)$(NC)" && exit 1)
	@echo "$(BLUE)→ Starting batch download from $(FILE)...$(NC)"
	python downloader.py -b "$(FILE)" $(ARGS)

# Show current configuration
show-config:
	@echo "$(BLUE)→ Current Configuration:$(NC)"
	python downloader.py --show-config

# Show version
version:
	@python downloader.py --version

# Install via pipx (global installation)
pipx-install:
	@echo "$(BLUE)→ Installing globally via pipx...$(NC)"
	pipx install .
	@echo "$(GREEN)✓ Global installation complete$(NC)"
	@echo "$(YELLOW)You can now run: tubetracks <url>$(NC)"

# Uninstall via pipx
pipx-uninstall:
	@echo "$(YELLOW)⚠ Removing global installation...$(NC)"
	pipx uninstall tubetracks
	@echo "$(GREEN)✓ Global installation removed$(NC)"

# Watch mode for development (auto-run tests on file changes)
watch:
	@echo "$(BLUE)→ Watching for changes (install ptw for auto-test)...$(NC)"
	@which ptw > /dev/null 2>&1 && ptw || \
	(echo "$(YELLOW)ptw not found. Install with: pip install pytest-watch$(NC)" && \
	 echo "$(BLUE)Alternatively, run: make test$(NC)")

# Pre-commit setup
pre-commit:
	@echo "$(BLUE)→ Setting up pre-commit hooks...$(NC)"
	@which pre-commit > /dev/null 2>&1 || (echo "$(YELLOW)Installing pre-commit...$(NC)" && pip install pre-commit)
	pre-commit install
	@echo "$(GREEN)✓ Pre-commit hooks installed$(NC)"
	@echo "$(YELLOW)Pre-commit will run checks before each git commit$(NC)"

# List available plugins
list-plugins:
	@echo "$(BLUE)→ Available Platform Plugins:$(NC)"
	python downloader.py --list-plugins

# Show plugin API documentation
plugin-docs:
	@echo "$(BLUE)→ Plugin API Documentation:$(NC)"
	@test -f PLUGIN_API.md || (echo "$(RED)✗ PLUGIN_API.md not found$(NC)" && exit 1)
	@echo "$(GREEN)View PLUGIN_API.md for detailed documentation$(NC)"
	@echo ""
	@echo "$(BLUE)Quick Reference:$(NC)"
	@echo "  - Create plugins in plugins/ directory"
	@echo "  - Inherit from BaseConverter class"
	@echo "  - Implement required methods: get_capabilities(), can_handle(), validate_url(), get_info(), download()"
	@echo "  - Register in plugins/__init__.py"
	@echo ""
	@echo "$(BLUE)Supported Platforms:$(NC)"
	python downloader.py --list-plugins | grep -E "^[A-Z]" | head -15

# Launch GUI application
gui:
	@echo "$(BLUE)→ Launching Desktop GUI...$(NC)"
	@test -f tubetracks_gui.py || (echo "$(RED)✗ tubetracks_gui.py not found$(NC)" && exit 1)
	@echo "$(GREEN)Starting GUI application...$(NC)"
	python tubetracks_gui.py

# Test GUI imports and dependencies
gui-test:
	@echo "$(BLUE)→ Testing GUI dependencies...$(NC)"
	@python -c "import tkinter; print('✓ tkinter available')" || (echo "$(RED)✗ tkinter not installed$(NC)" && exit 1)
	@python -c "import tubetracks_gui; print('✓ GUI module loads successfully')" || (echo "$(RED)✗ GUI module failed to load$(NC)" && exit 1)
	@echo "$(GREEN)✓ GUI dependencies satisfied$(NC)"

