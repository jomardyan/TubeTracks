# Copilot Instructions for AudioDownload-YT

## Project Architecture

**Multi-Platform Media Downloader** with plugin-based architecture supporting 9+ platforms (YouTube, TikTok, Instagram, SoundCloud, Spotify, Twitch, Dailymotion, Vimeo, Reddit).

### Core Components

1. **[downloader.py](../downloader.py)** (2,419 lines): Main CLI orchestrator
   - Handles quality presets (`QUALITY_PRESETS`: low/medium/high/best → bitrate)
   - Manages download lifecycle with retry logic and exponential backoff
   - Wraps yt-dlp with custom progress tracking via `DownloadProgress` class
   - Config system: `Config` dataclass + INI file loading from `~/.ytdownloader.conf`

2. **[plugins/](../plugins/)**: Platform-specific converters
   - **Base**: [plugins/base.py](../plugins/base.py) defines `BaseConverter` abstract class
   - **Registry**: `PluginRegistry` auto-discovers handlers via `can_handle(url)` method
   - **Auto-registration**: All plugins registered in `plugins/__init__.py::register_default_plugins()`
   - Each plugin implements: `get_capabilities()`, `validate_url()`, `get_info()`, `download()`

3. **[ytdownloader_gui.py](../ytdownloader_gui.py)** (973 lines): Tkinter desktop GUI
   - Threading model: Background worker threads with `queue.Queue` for UI updates
   - Cancellation via `threading.Event` checked in progress hooks
   - Uses [downloader.py](../downloader.py) as backend library (no CLI coupling)

### Critical Data Flows

- **URL → Plugin Selection**: `get_converter_for_url()` → iterates registry → first `can_handle()` match
- **Download Pipeline**: URL cleaning → info extraction → download → FFmpeg post-processing → metadata embedding
- **Archive System**: `DEFAULT_ARCHIVE_FILE` (~/.ytdownloader_archive.txt) prevents re-downloads
- **Error Classification**: `classify_error()` maps exceptions → `ErrorCode` enum → retry decisions

## Developer Workflows

### Testing & Quality

```bash
# Run full test suite (cross-platform matrix in CI)
make test                # pytest with coverage
make smoke-test         # Quick validation only
make lint               # ruff/flake8 style checks
make format             # black + isort auto-formatting
```

**Test Structure**: [tests/test_smoke.py](../tests/test_smoke.py) validates URL patterns, config loading, FFmpeg detection. No live download tests (network-free).

### Building & Packaging

```bash
make build              # python -m build → dist/
make publish            # twine upload to PyPI
```

**Entry Points** (pyproject.toml):
- `ytdownloader` / `ytdl` → `downloader:main`
- `ytdownloader-gui` → `ytdownloader_gui:main`

### GUI Development

```bash
make gui                # Launch desktop app
make gui-test           # Verify tkinter availability
```

**GUI Threading Pattern**:
```python
self._cancel_event = threading.Event()  # Checked in DownloadProgress.hook()
self._queue = queue.Queue()             # Background → UI thread communication
self._poll_queue()                       # Tkinter after() loop for updates
```

## Project-Specific Conventions

### Code Patterns

**Progress Tracking**: Always use `DownloadProgress` class with `progress_hook` parameter:
```python
progress_tracker = DownloadProgress(quiet=quiet, progress_callback=callback, cancel_event=cancel)
ydl_opts['progress_hooks'] = [progress_tracker.hook]
```

**Plugin Registration**: Add new platforms in [plugins/__init__.py](../plugins/__init__.py):
```python
plugins = [("youtube", YouTubeConverter()), ("newplatform", NewPlatformConverter())]
```

**Error Handling**: Use structured `DownloadResult` with `ErrorCode` enum (not raw exceptions):
```python
return DownloadResult(success=False, error_code=ErrorCode.NETWORK_ERROR, 
                      error_message="...", attempts=attempt)
```

### File Structure

- `plugins/*.py`: One file per platform, inherits `BaseConverter`
- `tests/test_*.py`: Pytest tests, no network calls, mock yt-dlp
- `.github/workflows/*.yml`: CI matrix tests Python 3.8-3.12 on ubuntu/windows/macos

### Configuration Management

**Precedence Order**:
1. CLI arguments (`argparse`)
2. `~/.ytdownloader.conf` (INI format, `RawConfigParser` to preserve `%(title)s` templates)
3. Hardcoded defaults in `Config` dataclass

**Archive System**: Enabled by default via `archive_file` parameter. Disable with `--no-archive`.

## Integration Points

### yt-dlp Wrapper Layer

- **Quality Mapping**: `QUALITY_PRESETS[quality]` → FFmpeg bitrate
- **Format Selection**: `format: 'bestaudio/best'` + `FFmpegExtractAudio` postprocessor
- **Progress Hooks**: Custom `DownloadProgress.hook()` intercepts yt-dlp callbacks
- **URL Cleaning**: `clean_youtube_url()` removes auto-generated mix/radio playlist params (`RDQM`, `RDMM`, etc.)

### FFmpeg Detection

Multi-path search in `check_ffmpeg()`:
1. `shutil.which('ffmpeg')` (PATH)
2. Windows: `cmd /c ffmpeg -version` (refresh PATH)
3. Common install paths: `C:/Program Files/ffmpeg`, WinGet packages

### External Dependencies

**Core** (requirements.txt):
- `yt-dlp>=2024.0.0`: Platform extraction engine
- `rich>=13.0.0`: Terminal UI (Progress, Console, Panel)

**Dev** (pyproject.toml `[project.optional-dependencies]`):
- pytest, pytest-cov, black, isort, ruff, bandit

## CI/CD Workflows

### [.github/workflows/build.yml](../.github/workflows/build.yml)

**Key Jobs**:
- `lint`: black/isort/flake8/pylint/mypy
- `security`: bandit, safety, pip-audit
- `build`: Test matrix (3.8-3.12 × ubuntu/windows/macos)
- `build-package`: Create wheel + sdist, verify with twine
- `test-install`: Install from wheel, test CLI commands

**Artifacts**: `python-package-distributions` (wheel + tarball)

### [.github/workflows/publish-pypi.yml](../.github/workflows/publish-pypi.yml)

Manual dispatch only (`workflow_dispatch`). Requires secrets:
- `TEST_PYPI_API_TOKEN` (testpypi)
- `PYPI_API_TOKEN` (production)

## Plugin Development Quick Reference

See [PLUGIN_API.md](../PLUGIN_API.md) for full docs. Minimal template:

```python
from plugins.base import BaseConverter, PluginCapabilities, ContentType
import re

class MyPlatformConverter(BaseConverter):
    def get_capabilities(self):
        return PluginCapabilities(
            name="MyPlatform", version="1.0.0", platform="MyPlatform",
            description="Download from MyPlatform",
            supported_content_types=[ContentType.AUDIO],
            url_patterns=[r"myplatform\.com"],
            supports_playlists=False, output_formats=["mp3", "m4a"]
        )
    
    def can_handle(self, url): return "myplatform.com" in url.lower()
    def validate_url(self, url): return (True, "") if self.can_handle(url) else (False, "Invalid")
    def get_info(self, url, **kwargs): return {"title": "...", "duration": 123}
    def download(self, url, output_path, quality="medium", format="mp3", **kwargs):
        # Use yt-dlp or custom logic
        return (True, "/path/to/file.mp3", None)  # (success, path, error)
```

## Important Guidelines

### Documentation Policy

**DO NOT create new markdown files** unless explicitly requested. The project already has comprehensive documentation:
- [README.md](../README.md): User guide and feature overview
- [PLUGIN_API.md](../PLUGIN_API.md): Plugin development reference
- [GITHUB_ACTIONS_SETUP.md](../GITHUB_ACTIONS_SETUP.md): CI/CD configuration
- [PyPI_PUBLISHING.md](../PyPI_PUBLISHING.md), [PYPI_GUIDE.md](../PYPI_GUIDE.md): Publishing guides
- [CHANGELOG.md](../CHANGELOG.md): Version history

When making code changes, update existing documentation inline via docstrings and comments. Do not generate summary files, change logs, or task completion reports.

## Common Development Tasks

**Add new quality preset**: Update `QUALITY_PRESETS` dict in [downloader.py](../downloader.py)

**Add new format**: Update `SUPPORTED_FORMATS` list + FFmpeg postprocessor mapping

**Modify GUI layout**: Edit `App._build_ui()` in [ytdownloader_gui.py](../ytdownloader_gui.py)

**Change concurrent downloads**: Modify `ThreadPoolExecutor(max_workers=...)` in `_download_playlist()`

**Update version**: Edit `__version__` in [downloader.py](../downloader.py) and `version` in [pyproject.toml](../pyproject.toml)

Avoid using emojis.