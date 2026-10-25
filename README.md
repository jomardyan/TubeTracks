# TubeTracks

<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Build Status](https://github.com/jomardyan/TubeTracks/actions/workflows/build.yml/badge.svg)](https://github.com/jomardyan/TubeTracks/actions)
[![Code style: Ruff](https://img.shields.io/badge/code%20style-Ruff-d7ff64.svg)](https://docs.astral.sh/ruff/)

**A professional-grade, multi-platform media downloader for audio extraction and conversion.**

Extract audio from YouTube, Spotify, SoundCloud, and 9+ platforms with precise quality control, batch processing, and an extensible plugin architecture.

</div>

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [System Requirements](#system-requirements)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Supported Platforms](#supported-platforms)
- [API Reference](#api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

TubeTracks is a command-line and GUI application designed for reliable audio extraction from popular media platforms. Built on top of [yt-dlp](https://github.com/yt-dlp/yt-dlp) and [FFmpeg](https://ffmpeg.org/), it provides a streamlined workflow for downloading, converting, and organizing audio content.

### Why TubeTracks?

| Challenge | Solution |
|-----------|----------|
| Complex yt-dlp command syntax | Simple CLI flags and intuitive GUI |
| No visual progress feedback | Real-time progress bars and detailed logging |
| Manual duplicate tracking | Built-in archive system |
| Platform-specific quirks | Unified plugin architecture |
| Inconsistent metadata | Automatic ID3 tagging and artwork embedding |

---

## Key Features

### Core Functionality

- **Multi-Platform Support** — YouTube, TikTok, Instagram, SoundCloud, Spotify, Twitch, Dailymotion, Vimeo, Reddit
- **Quality Control** — Four preset levels (128–320 kbps) plus best encoder quality
- **Format Conversion** — MP3, M4A, FLAC, WAV, OGG output via FFmpeg
- **Batch Processing** — Concurrent downloads with configurable thread count (1–5)
- **Dual Interface** — Full-featured CLI and cross-platform GUI (Tkinter)
- **Smart Deduplication** — Archive system prevents re-downloading content

### Advanced Capabilities

| Feature | Description |
|---------|-------------|
| **Plugin Architecture** | Extensible system for adding new platforms |
| **Network Controls** | Proxy support, rate limiting, cookie authentication |
| **Metadata Embedding** | Automatic ID3 tags and cover art |
| **Configuration Files** | INI-based persistent settings |
| **Error Recovery** | Intelligent retry with exponential backoff |
| **Dry Run Mode** | Preview operations without downloading |

---

## System Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10 or higher (3.11+ recommended) |
| FFmpeg | Latest stable release |
| OS | Windows, macOS, or Linux |

**Dependencies** (installed automatically):
- `yt-dlp[default] >= 2026.10.21`
- `rich >= 15.0.0, < 16`

---

## Installation

### From PyPI (Recommended)

```bash
pip install tubetracks
```

### From Source

```bash
git clone https://github.com/jomardyan/TubeTracks.git
cd TubeTracks
pip install -r requirements.txt
```

### FFmpeg Setup

TubeTracks requires FFmpeg for audio conversion.

<details>
<summary><strong>Windows</strong></summary>

```powershell
winget install Gyan.FFmpeg
# or
choco install ffmpeg
```
</details>

<details>
<summary><strong>macOS</strong></summary>

```bash
brew install ffmpeg
```
</details>

<details>
<summary><strong>Linux</strong></summary>

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch
sudo pacman -S ffmpeg
```
</details>

### YouTube JavaScript Support

Current yt-dlp releases need a supported JavaScript runtime for full YouTube support.
The default dependencies include the yt-dlp EJS challenge scripts. Install
[Deno](https://docs.deno.com/runtime/getting_started/installation/) as well, or use
yt-dlp's optional runtime package in the same Python environment:

```bash
python -m pip install --upgrade "yt-dlp[default,deno]"
```

Tkinter is provided with most Python installers. On Debian/Ubuntu, install
`python3-tk` separately if needed.

### Verify Installation

```bash
tubetracks --version
ffmpeg -version
```

---

## Usage

### Command Line Interface

**Basic operations:**

```bash
# Download audio from URL
tubetracks "https://www.youtube.com/watch?v=VIDEO_ID"

# Specify quality and format
tubetracks -q high -f flac "URL"

# Download playlist
tubetracks -p "PLAYLIST_URL"

# Batch download from file
tubetracks -b urls.txt -o ./music
```

**Advanced options:**

```bash
# Custom output template
tubetracks -o ~/Music -t "%(artist)s - %(title)s" "URL"

# Network configuration
tubetracks --proxy socks5://127.0.0.1:1080 --limit-rate 1M "URL"

# Preview without downloading
tubetracks --dry-run "URL"
```

### Graphical Interface

```bash
tubetracks-gui
# or
python tubetracks_gui.py
```

### Python API

```python
from downloader import download_audio

result = download_audio(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="./downloads",
    quality="high",
    audio_format="mp3"
)

if result.success:
    print(f"Saved: {result.output_path}")
```

See [LIBRARY_USAGE.md](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md) for complete API documentation.

---

## Configuration

TubeTracks loads INI-format settings from `~/.ytdownloader.conf`, preserving
compatibility with existing installations. Use `--config path/to/settings.conf`
to select another file. Explicit CLI options override saved settings.
The default download archive is `~/.ytdownloader_archive.txt`.

**Example configuration:**

```ini
[download]
quality = high
format = mp3
output = ~/Music/TubeTracks
template = %(artist)s - %(title)s.%(ext)s
embed_metadata = true
embed_thumbnail = true
retries = 3

[archive]
use_archive = true
archive_file = ~/.ytdownloader_archive.txt

[network]
# proxy = socks5://127.0.0.1:1080
# rate_limit = 1M
```

**Manage settings:**

```bash
tubetracks --show-config    # Display current configuration
tubetracks --save-config    # Save to config file
```

### Quality Presets

| Preset | Bitrate | Use Case |
|--------|---------|----------|
| `low` | 128 kbps | Podcasts, spoken word |
| `medium` | 192 kbps | General listening (default) |
| `high` | 320 kbps | High-fidelity music |
| `best` | Best encoder quality | Highest quality supported by the selected codec |

---

## Supported Platforms

| Platform | Status | Playlists | Authentication |
|----------|:------:|:---------:|:--------------:|
| YouTube | Stable | Yes | No |
| TikTok | Stable | Yes | No |
| Instagram | Stable | No | Optional |
| SoundCloud | Stable | Yes | No |
| Spotify | Stable | Yes | Optional |
| Twitch | Stable | No | No |
| Dailymotion | Stable | Yes | No |
| Vimeo | Stable | Yes | Optional |
| Reddit | Stable | No | No |

```bash
tubetracks --list-plugins  # View all available plugins
```

---

## API Reference

### Additional Documentation

| Document | Description |
|----------|-------------|
| [LIBRARY_USAGE.md](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md) | Python API reference |
| [PLUGIN_API.md](https://github.com/jomardyan/TubeTracks/blob/main/PLUGIN_API.md) | Plugin development guide |
| [CHANGELOG.md](https://github.com/jomardyan/TubeTracks/blob/main/CHANGELOG.md) | Version history |

---

## Development

### Environment Setup

```bash
git clone https://github.com/jomardyan/TubeTracks.git
cd TubeTracks
python -m venv .venv
# Activate .venv, then:
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The suite includes local media conversion tests and Tkinter lifecycle tests.
Install FFmpeg and ffprobe to run the media tests. On headless Linux, install
Xvfb and run `xvfb-run -a python -m pytest` to include the GUI tests.
Tests use generated media served on loopback; they do not contact external media
platforms. Live platform availability and account authentication need separate
manual checks. CI runs the suite on Python 3.10–3.14 on Linux, macOS and Windows.

### Commands

| Command | Description |
|---------|-------------|
| `make test` | Run test suite |
| `make lint` | Check code style |
| `make format` | Auto-format code |
| `make build` | Build distribution |
| `make clean` | Remove artifacts |

---

## Contributing

Contributions are welcome. Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/improvement`)
3. Commit changes with clear messages
4. Add tests for new functionality
5. Ensure `make test` passes
6. Submit a pull request

**Guidelines:**
- Use [Ruff](https://docs.astral.sh/ruff/) for linting, import sorting, and formatting
- Include tests for new features
- Update documentation as needed

**Resources:**
- [Issue Tracker](https://github.com/jomardyan/TubeTracks/issues)
- [Pull Requests](https://github.com/jomardyan/TubeTracks/pulls)
- [Discussions](https://github.com/jomardyan/TubeTracks/discussions)

---

## License

This project is licensed under the **GNU General Public License v3.0 or later** (GPLv3+).

See [LICENSE](https://github.com/jomardyan/TubeTracks/blob/main/LICENSE) for the full text.

### Legal Notice

TubeTracks is provided for **educational and personal use only**. Users are responsible for ensuring compliance with:

- Applicable copyright laws
- Platform terms of service
- Local and international regulations

The developers assume no liability for misuse of this software.

---

## Acknowledgments

Built with:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — Media extraction
- [FFmpeg](https://ffmpeg.org/) — Audio/video processing
- [Rich](https://github.com/Textualize/rich) — Terminal formatting

---

## Support

| Resource | Link |
|----------|------|
| Documentation | [README.md](https://github.com/jomardyan/TubeTracks/blob/main/README.md) |
| Bug Reports | [Issue Tracker](https://github.com/jomardyan/TubeTracks/issues) |
| Questions | [Discussions](https://github.com/jomardyan/TubeTracks/discussions) |

**Project Status:** Active Development  
**Current Version:** 1.6.0<br>
**Maintainer:** [Hayk Jomardyan](https://github.com/jomardyan)

---

<div align="center">

[![Star on GitHub](https://img.shields.io/github/stars/jomardyan/TubeTracks?style=social)](https://github.com/jomardyan/TubeTracks)

</div>
