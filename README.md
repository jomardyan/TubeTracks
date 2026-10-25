# TubeTracks

[![PyPI version](https://img.shields.io/pypi/v/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Build Status](https://github.com/jomardyan/TubeTracks/actions/workflows/build.yml/badge.svg)](https://github.com/jomardyan/TubeTracks/actions/workflows/build.yml)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-d7ff64.svg)](https://docs.astral.sh/ruff/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Download and convert media with a command-line interface, a Tkinter desktop app,
or a Python API. TubeTracks combines [yt-dlp](https://github.com/yt-dlp/yt-dlp)
extraction with [FFmpeg](https://ffmpeg.org/) conversion and nine platform plugins.

**Source version: 1.6.0.** The PyPI badge shows the latest published package.

## Contents

- [What's new in 1.6.0](#whats-new-in-160)
- [Features](#features)
- [Requirements](#requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Platform plugins](#platform-plugins)
- [Development and testing](#development-and-testing)
- [Publishing to PyPI](#publishing-to-pypi)
- [Documentation and support](#documentation-and-support)
- [License](#license)

## What's new in 1.6.0

- Updated yt-dlp and Rich dependencies, with Python 3.10+ support and yt-dlp's
  default extraction, JavaScript challenge, and metadata dependencies.
- Shared conversion behavior across platform plugins, including format selection,
  cookies, proxies, rate limits, archives, metadata, and artwork.
- Download results report the final converted file path and size.
- Connected CLI batch, playlist, preview, configuration, and concurrency options.
- Improved playlist previews, cancellable retry waits, GUI shutdown, and concurrent
  downloads from the desktop app.
- Ruff-based linting and formatting, updated packaging, and CI configured for
  Python 3.10–3.14 on Linux, macOS, and Windows.

See the [changelog](https://github.com/jomardyan/TubeTracks/blob/main/CHANGELOG.md)
for release details.

## Features

| Feature | Details |
|---------|---------|
| Audio conversion | MP3, M4A, FLAC, WAV, Ogg Vorbis, and Opus |
| Video output | MP4 using compatible source streams and FFmpeg remuxing |
| Quality presets | Low (128 kbps), medium (192 kbps), high (320 kbps), and best encoder quality |
| Batch downloads | Read URLs from a UTF-8 file; process 1–5 independent URLs concurrently |
| Playlists | Enable full-playlist processing with `--playlist` on supported platforms |
| Preview | Inspect metadata and resolved output paths with `--dry-run` |
| Metadata and artwork | Embed supported tags and cover art; artwork is skipped for WAV |
| Download archive | Track completed items to avoid downloading them again |
| Network options | Proxy, rate limiting, and Netscape-format cookie files |
| Interfaces | CLI, Tkinter GUI, and an importable Python API |

`ogg` and `vorbis` both produce Ogg Vorbis files with an `.ogg` extension.
Bitrate presets apply to lossy audio conversion. FLAC/WAV output and the `best`
preset cannot restore quality missing from the source.

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+; 3.11 or newer recommended |
| Operating system | Windows, macOS, or Linux |
| FFmpeg and ffprobe | Available on `PATH` for conversion and media inspection |
| Tkinter | Required for the desktop GUI |
| JavaScript runtime | A supported runtime such as Deno for full YouTube extraction support |

Python dependencies are installed automatically:

- `yt-dlp[default] >= 2026.10.21`, including EJS challenge scripts and metadata dependencies.
- `rich >= 15.0.0, < 16` for terminal output.

## Installation

### Install or upgrade from PyPI

Use a virtual environment when installing Python packages:

```bash
python -m venv .venv
```

Activate it for your shell:

| Shell | Command |
|-------|---------|
| macOS/Linux | `source .venv/bin/activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| Windows Command Prompt | `.venv\Scripts\activate.bat` |

Then install the latest published release:

```bash
python -m pip install --upgrade pip
python -m pip install --upgrade tubetracks
```

### Install from source

To use the checked-out source, including changes awaiting publication:

```bash
git clone https://github.com/jomardyan/TubeTracks.git
cd TubeTracks
# Activate a Python virtual environment, then:
python -m pip install .
```

### Install FFmpeg

| Platform | Example command |
|----------|-----------------|
| Windows | `winget install Gyan.FFmpeg` |
| macOS | `brew install ffmpeg` |
| Debian/Ubuntu | `sudo apt update && sudo apt install ffmpeg` |
| Fedora | `sudo dnf install ffmpeg` |
| Arch Linux | `sudo pacman -S ffmpeg` |

On Debian/Ubuntu, install `python3-tk` if Tkinter is unavailable.

### Set up YouTube JavaScript support

The EJS challenge scripts are included with the default yt-dlp dependencies.
Install [Deno](https://docs.deno.com/runtime/getting_started/installation/) as the
JavaScript runtime, or install yt-dlp's optional runtime package in the same
Python environment:

```bash
python -m pip install --upgrade "yt-dlp[default,deno]"
```

### Verify the installation

```bash
tubetracks --version
tubetracks --list-plugins
ffmpeg -version
ffprobe -version
```

## Usage

### Command line

```bash
# Download audio as MP3 with the default medium-quality preset
tubetracks "https://www.youtube.com/watch?v=VIDEO_ID"

# Choose a format and quality preset
tubetracks -q high -f flac "https://www.youtube.com/watch?v=VIDEO_ID"

# Process a full playlist
tubetracks --playlist "https://www.youtube.com/playlist?list=PLAYLIST_ID"

# Download independent URLs concurrently
tubetracks --batch-file urls.txt --concurrent-downloads 3 --output ./music

# Resolve metadata and output filenames without downloading media
tubetracks --dry-run "https://www.youtube.com/watch?v=VIDEO_ID"

# Use a filename template, including its output extension
tubetracks --output ./music --template "%(artist)s - %(title)s.%(ext)s" "URL"

# Set network options
tubetracks --proxy socks5://127.0.0.1:1080 --limit-rate 1M "URL"
tubetracks --cookies-file cookies.txt "URL"

# Disable archive tracking or embedded artwork for a run
tubetracks --no-use-archive --no-embed-thumbnail "URL"

# List all available options
tubetracks --help
```

Replace `VIDEO_ID`, `PLAYLIST_ID`, and `URL` with actual media identifiers or URLs.
Batch files contain one URL per line; blank lines and lines starting with `#`
are ignored. Concurrency applies to independent input URLs; yt-dlp processes the
entries within each playlist.

The `ytdl` and `audiodownload` commands are aliases for `tubetracks`.

### Desktop GUI

```bash
tubetracks-gui
```

From a source checkout, you can also run `python tubetracks_gui.py`.
The GUI supports URL entry, batch files, previews, output settings, concurrent
input URLs, progress logs, and cancellation.

### Python API

```python
from downloader import download_audio

result = download_audio(
    url="https://www.youtube.com/watch?v=VIDEO_ID",
    output_dir="./downloads",
    quality="high",
    audio_format="mp3",
)

if result.skipped:
    print("Already in the download archive")
elif result.success:
    print(f"Saved: {result.output_path} ({result.file_size} bytes)")
else:
    print(f"{result.error_code.name}: {result.error_message}")
```

The CLI and GUI use saved configuration settings. Python API callers pass their
options explicitly; archive tracking can be enabled with `archive_file="archive.txt"`.
See the [library guide](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md)
for playlists, progress callbacks, retries, network options, and cancellation.

## Configuration

Settings load from `~/.ytdownloader.conf`. Use `--config path/to/settings.conf`
to select another file. Explicit CLI options override saved values.
The CLI and GUI use `~/.ytdownloader_archive.txt` as the default download archive.

```ini
[download]
quality = high
format = mp3
output = ~/Music/TubeTracks
template = %(artist)s - %(title)s.%(ext)s
retries = 3
concurrent_downloads = 2
embed_metadata = true
embed_thumbnail = true

[archive]
use_archive = true
archive_file = ~/.ytdownloader_archive.txt

[network]
# proxy = socks5://127.0.0.1:1080
# rate_limit = 1M
# cookies_file = cookies.txt
```

```bash
# Show settings, including explicit overrides
tubetracks --show-config

# Save settings to a selected file
tubetracks --config settings.conf -q high --concurrent-downloads 2 --save-config

# Use that file for a download
tubetracks --config settings.conf "URL"
```

## Platform plugins

The bundled plugins route matching URLs to yt-dlp. Extraction depends on
upstream platform support, content access, and any required cookies.

| Plugin | Playlist handling declared by the plugin |
|--------|:----------------------------------------:|
| YouTube | Yes |
| TikTok | Yes |
| Instagram | No |
| SoundCloud | Yes |
| Spotify | Yes |
| Twitch | No |
| Dailymotion | Yes |
| Vimeo | Yes |
| Reddit | No |

The Spotify plugin recognizes track, playlist, and album URLs and delegates to
yt-dlp. It does not implement Spotify-to-YouTube matching or authenticated music
track downloads. Recognizing a URL does not guarantee that its content can be downloaded.

Use `tubetracks --list-plugins` to inspect the installed plugins. To add a platform,
see the [plugin API guide](https://github.com/jomardyan/TubeTracks/blob/main/PLUGIN_API.md).

## Development and testing

After cloning the repository and activating a virtual environment:

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

The suite includes CLI and configuration tests, plugin routing, downloader
lifecycle checks, real yt-dlp/FFmpeg conversions using generated media served on
loopback, and Tkinter GUI lifecycle/concurrency checks. It does not contact
external media services.

Install FFmpeg, ffprobe, and Tkinter to run all tests. On headless Linux, install
Xvfb and run:

```bash
xvfb-run -a python -m pytest
```

Without FFmpeg or a graphical display, the corresponding integration tests are
skipped. CI is configured to provide these dependencies and test Python 3.10–3.14
on Linux, macOS, and Windows. The 1.6.0 release-preparation run passed all **241 tests
with no skips** on Linux; this does not establish live platform availability.

| Command | Purpose |
|---------|---------|
| `make test` | Run the complete test suite |
| `make coverage` | Generate coverage reports |
| `make lint` | Check Ruff linting and formatting |
| `make format` | Sort imports and format Python code |
| `make security` | Run Bandit and the installed-dependency audit |
| `make build` | Clean and build source and wheel distributions |

Contributions should include relevant tests and documentation updates. Run the
suite and lint checks before opening a pull request.

## Publishing to PyPI

The [Publish to PyPI workflow](https://github.com/jomardyan/TubeTracks/actions/workflows/publish-pypi.yml)
is started manually from GitHub Actions:

1. Merge the release changes, including a version that has not been uploaded before.
2. Configure `TEST_PYPI_API_TOKEN` for TestPyPI or `PYPI_API_TOKEN` for production
   in the repository's Actions secrets.
3. Choose **Run workflow**, select the release ref, set `environment` to
   `testpypi` or `pypi`, and leave `skip_tests` set to `false`.
4. Check the test, build, strict Twine-validation, and upload results.

The workflow defaults to TestPyPI. A completed build validates distributions;
the upload step must succeed before the version is available from the selected index.
Already-uploaded files cause the upload to fail, preventing silent duplicate-version skips.

## Documentation and support

| Resource | Link |
|----------|------|
| Python API | [Library usage](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md) |
| Plugin development | [Plugin API](https://github.com/jomardyan/TubeTracks/blob/main/PLUGIN_API.md) |
| Release history | [Changelog](https://github.com/jomardyan/TubeTracks/blob/main/CHANGELOG.md) |
| Bug reports and feature requests | [GitHub Issues](https://github.com/jomardyan/TubeTracks/issues) |
| Questions | [GitHub Discussions](https://github.com/jomardyan/TubeTracks/discussions) |
| Maintainer | [Hayk Jomardyan](https://github.com/jomardyan) |

## License

This project is licensed under the **GNU General Public License v3.0 or later**
(GPLv3+). See [LICENSE](https://github.com/jomardyan/TubeTracks/blob/main/LICENSE).

TubeTracks is provided for educational and personal use. Users are responsible
for complying with applicable copyright laws, platform terms, and local regulations.
The developers assume no liability for misuse of this software.
