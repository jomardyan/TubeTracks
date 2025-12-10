.PHONY: help install install-dev test lint clean build publish run

# Default target
help:
	@echo "YouTube MP3 Downloader - Makefile"
	@echo ""
	@echo "Usage:"
	@echo "  make install       Install the package and dependencies"
	@echo "  make install-dev   Install with development dependencies"
	@echo "  make test          Run tests"
	@echo "  make lint          Run linter (if available)"
	@echo "  make clean         Remove build artifacts"
	@echo "  make build         Build distribution packages"
	@echo "  make run URL=<url> Download from a YouTube URL"
	@echo ""
	@echo "Examples:"
	@echo "  make run URL='https://www.youtube.com/watch?v=dQw4w9WgXcQ'"
	@echo "  make run URL='https://www.youtube.com/watch?v=VIDEO_ID' ARGS='-q high -f flac'"

# Install the package
install:
	pip install -e .

# Install with dev dependencies
install-dev:
	pip install -e ".[dev]"

# Run tests
test:
	python -m pytest tests/ -v

# Run smoke tests only
smoke-test:
	python -m pytest tests/test_smoke.py -v

# Lint (optional - requires ruff or flake8)
lint:
	@which ruff > /dev/null 2>&1 && ruff check . || \
	which flake8 > /dev/null 2>&1 && flake8 . || \
	echo "No linter found (install ruff or flake8)"

# Clean build artifacts
clean:
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info/
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Build distribution
build: clean
	python -m build

# Publish to PyPI (requires twine)
publish: build
	python -m twine upload dist/*

# Run the downloader
run:
ifndef URL
	@echo "Error: URL is required"
	@echo "Usage: make run URL='https://www.youtube.com/watch?v=VIDEO_ID'"
	@exit 1
endif
	python youtube_mp3_downloader.py $(ARGS) "$(URL)"

# Run with dry-run
dry-run:
ifndef URL
	@echo "Error: URL is required"
	@echo "Usage: make dry-run URL='https://www.youtube.com/watch?v=VIDEO_ID'"
	@exit 1
endif
	python youtube_mp3_downloader.py --dry-run "$(URL)"

# Show current configuration
show-config:
	python youtube_mp3_downloader.py --show-config

# Show version
version:
	python youtube_mp3_downloader.py --version

# Install via pipx (global installation)
pipx-install:
	pipx install .

# Uninstall via pipx
pipx-uninstall:
	pipx uninstall ytdownloader
