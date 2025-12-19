# 🎵 TubeTracks

<div align="center">

[![PyPI version](https://img.shields.io/pypi/v/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![PyPI downloads](https://img.shields.io/pypi/dm/tubetracks.svg)](https://pypi.org/project/tubetracks/)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Build Status](https://github.com/jomardyan/TubeTracks/actions/workflows/build.yml/badge.svg)](https://github.com/jomardyan/TubeTracks/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Professional multi-platform media downloader with advanced quality control and batch processing**

Download audio from YouTube, Spotify, SoundCloud, and 6+ other platforms with enterprise-grade features and an intuitive interface.

[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Features](#-features) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## ✨ Features

### Core Capabilities

- 🌐 **Multi-Platform Support** — YouTube, TikTok, Instagram, SoundCloud, Spotify, Twitch, Dailymotion, Vimeo, Reddit
- 🎚️ **Quality Control** — 4 preset levels (128kbps - 320kbps) plus original quality
- 🔄 **Format Conversion** — MP3, M4A, FLAC, WAV, OGG via FFmpeg
- 📋 **Batch Processing** — Process multiple URLs with concurrent downloads (1-5 threads)
- 🎨 **Dual Interface** — Professional CLI and intuitive GUI (Tkinter)
- 💾 **Smart Caching** — Archive system prevents duplicate downloads
- 🔐 **Network Features** — Proxy support, rate limiting, cookie-based authentication
- 🏷️ **Rich Metadata** — Automatic ID3 tags and embedded artwork
- 🔌 **Plugin Architecture** — Extensible system for adding platforms
- ⚡ **Performance** — Concurrent downloads, retry logic, error recovery

### Advanced Features

- **Configuration Management** — INI-based config files with precedence system
- **Comprehensive Logging** — Detailed logs with configurable verbosity
- **Progress Tracking** — Real-time progress bars and status updates
- **Dry Run Mode** — Preview downloads without actual processing
- **Template System** — Customizable filename templates
- **Error Handling** — Intelligent retry with exponential backoff
- **Cross-Platform** — Windows, macOS, Linux support

---

## 📋 Requirements

- **Python** 3.8 or higher
- **FFmpeg** (latest stable version)
- **Dependencies** — Automatically installed via pip
  - `yt-dlp >= 2024.0.0`
  - `rich >= 13.0.0`

---

## 🚀 Installation

### Method 1: PyPI (Recommended)

Install the latest stable release from PyPI:

```bash
pip install tubetracks
```

### Method 2: From Source

For development or latest features:

```bash
# Clone the repository
git clone https://github.com/jomardyan/TubeTracks.git
cd TubeTracks

# Install with make (recommended)
make install

# Or install manually
pip install -r requirements.txt
```

### FFmpeg Installation

TubeTracks requires FFmpeg for audio conversion:

**Automated Installation (PowerShell - all platforms):**
```powershell
pwsh ./install_ffmpeg.ps1
```

**Platform-Specific:**

<details>
<summary><b>Windows</b></summary>

```powershell
# Using winget (Windows 10+)
winget install Gyan.FFmpeg

# Using chocolatey
choco install ffmpeg
```
</details>

<details>
<summary><b>macOS</b></summary>

```bash
# Using Homebrew
brew install ffmpeg
```
</details>

<details>
<summary><b>Linux</b></summary>

```bash
# Debian/Ubuntu
sudo apt update && sudo apt install ffmpeg

# Fedora
sudo dnf install ffmpeg

# Arch Linux
sudo pacman -S ffmpeg
```
</details>

### Verify Installation

```bash
python --version    # Should be 3.8+
ffmpeg -version     # Verify FFmpeg is installed
tubetracks --version  # Test TubeTracks installation
```

---

## 🎯 Quick Start

### Command Line Interface

**Basic Usage:**

```bash
# Download single video (PyPI installation)
tubetracks "https://www.youtube.com/watch?v=VIDEO_ID"

# Download single video (from source)
python downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"

# High quality FLAC
tubetracks -q high -f flac "VIDEO_URL"

# Download entire playlist
tubetracks -p "PLAYLIST_URL"

# Batch download from file
tubetracks -b urls.txt -o ./music
```

**Advanced Usage:**

```bash
# Custom output directory and filename template
tubetracks -o ~/Music -t "%(artist)s - %(title)s" "URL"

# Use proxy with rate limiting
tubetracks --proxy socks5://127.0.0.1:1080 --limit-rate 1M "URL"

# Preview without downloading
tubetracks --dry-run "URL"

# Maximum retries with custom archive
tubetracks --retries 5 --archive ~/my-archive.txt "URL"
```

### Graphical User Interface

Launch the desktop application:

```bash
# PyPI installation
tubetracks-gui

# From source
python tubetracks_gui.py

# Or using Make
make gui
```

### Python Library

Integrate TubeTracks into your Python projects:

```python
from downloader import download_audio, DownloadResult

# Simple download
result = download_audio(
    url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    output_dir="./downloads",
    quality="high",
    audio_format="mp3"
)

if result.success:
    print(f"Downloaded: {result.output_path}")
else:
    print(f"Failed: {result.error_message}")
```

See [LIBRARY_USAGE.md](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md) for complete API documentation.

---

## 📖 Documentation

### Configuration

TubeTracks supports configuration files for persistent settings:

**Configuration Locations** (in order of precedence):
1. `~/.tubetracks.conf`
2. `~/.config/tubetracks/config.conf`
3. `./.tubetracks.conf`

**Example Configuration:**

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
archive_file = ~/.tubetracks_archive.txt

[network]
# proxy = socks5://127.0.0.1:1080
# rate_limit = 1M
# cookies_file = ~/cookies.txt

[logging]
# log_file = ~/tubetracks.log
```

**Manage Configuration:**

```bash
# View current configuration
tubetracks --show-config

# Save current settings to config file
tubetracks --save-config
```

### Quality Presets

| Preset | Bitrate | Best For |
|--------|---------|----------|
| `low` | 128 kbps | Podcasts, audiobooks, voice content |
| `medium` | 192 kbps | General listening (default) |
| `high` | 320 kbps | High-quality music |
| `best` | Original | Archival, lossless formats |

### Supported Platforms

| Platform | Status | Playlist Support | Auth Required |
|----------|--------|------------------|---------------|
| **YouTube** | ✅ Stable | ✅ Yes | ❌ No |
| **TikTok** | ✅ Stable | ✅ Yes | ❌ No |
| **Instagram** | ✅ Stable | ❌ No | ⚠️ Optional |
| **SoundCloud** | ✅ Stable | ✅ Yes | ❌ No |
| **Spotify** | ✅ Stable | ✅ Yes | ⚠️ Optional |
| **Twitch** | ✅ Stable | ❌ No | ❌ No |
| **Dailymotion** | ✅ Stable | ✅ Yes | ❌ No |
| **Vimeo** | ✅ Stable | ✅ Yes | ⚠️ Optional |
| **Reddit** | ✅ Stable | ❌ No | ❌ No |

**View all available plugins:**
```bash
tubetracks --list-plugins
```

### Additional Documentation

- **[Library API Documentation](https://github.com/jomardyan/TubeTracks/blob/main/LIBRARY_USAGE.md)** — Python API reference
- **[Plugin Development Guide](https://github.com/jomardyan/TubeTracks/blob/main/PLUGIN_API.md)** — Create custom platform plugins
- **[Changelog](https://github.com/jomardyan/TubeTracks/blob/main/CHANGELOG.md)** — Version history and release notes

---

## 🛠️ Development

### Setup Development Environment

```bash
# Clone repository
git clone https://github.com/jomardyan/TubeTracks.git
cd TubeTracks

# Install development dependencies
pip install -r requirements.txt
pip install -e ".[dev]"
```

### Testing

```bash
# Run all tests
make test

# Quick validation
make smoke-test

# Coverage report
make coverage

# Test specific module
pytest tests/test_downloader.py -v
```

### Code Quality

```bash
# Format code
make format

# Lint code
make lint

# Run all checks (format + lint + test)
make check

# Security scan
make security
```

### Build and Distribution

```bash
# Build package
make build

# Clean build artifacts
make clean

# Build documentation
make docs
```

---

## 🤝 Contributing

We welcome contributions! TubeTracks is an open-source project that thrives on community involvement.

### How to Contribute

1. **Fork the repository** on GitHub
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** with clear commit messages
4. **Add tests** for new functionality
5. **Run the test suite** (`make test`)
6. **Submit a pull request** with a clear description

### Contribution Guidelines

- Follow the existing code style (enforced by `black` and `isort`)
- Write clear, concise commit messages
- Add tests for new features
- Update documentation as needed
- Ensure all tests pass before submitting PR

### Development Resources

- **[Issue Tracker](https://github.com/jomardyan/TubeTracks/issues)** — Report bugs or request features
- **[Pull Requests](https://github.com/jomardyan/TubeTracks/pulls)** — Submit code contributions
- **[Discussions](https://github.com/jomardyan/TubeTracks/discussions)** — Ask questions or share ideas

---

## ⚖️ Legal & Compliance

### Disclaimer

**TubeTracks is provided for educational and personal use only.** Users are solely responsible for ensuring their usage complies with:

- Applicable copyright laws and intellectual property rights
- Platform terms of service and usage policies
- Local, national, and international regulations

The software developers and contributors assume **no responsibility or liability** for:
- Any misuse of this software
- Legal violations or consequences arising from usage
- Damages or losses incurred from using this software

### User Responsibilities

By using TubeTracks, you acknowledge that:

✅ You have the legal right to download the content  
✅ You will respect copyright laws and intellectual property rights  
✅ You will comply with platform terms of service  
✅ You understand the developers are not liable for your actions  

### License

This project is licensed under the **GNU General Public License v3.0 or later** (GPLv3+).

See [LICENSE](https://github.com/jomardyan/TubeTracks/blob/main/LICENSE) for the full license text.

---

## 🙏 Acknowledgments

TubeTracks is built with and inspired by excellent open-source projects:

- **[yt-dlp](https://github.com/yt-dlp/yt-dlp)** — Powerful media extraction engine
- **[FFmpeg](https://ffmpeg.org/)** — Industry-standard audio/video processing
- **[Rich](https://github.com/Textualize/rich)** — Beautiful terminal formatting

---

## 📞 Support

### Getting Help

- 📖 **[Documentation](https://github.com/jomardyan/TubeTracks/blob/main/README.md)** — Start here
- 🐛 **[Issue Tracker](https://github.com/jomardyan/TubeTracks/issues)** — Report bugs
- 💬 **[Discussions](https://github.com/jomardyan/TubeTracks/discussions)** — Ask questions

### Project Status

- **Current Version:** 1.5.1
- **Status:** Active development
- **Python Support:** 3.8, 3.9, 3.10, 3.11, 3.12
- **Platforms:** Windows, macOS, Linux

---

<div align="center">

**[⬆ Back to Top](#-tubetracks)**

Made with ❤️ by the TubeTracks community

[![Star on GitHub](https://img.shields.io/github/stars/jomardyan/TubeTracks?style=social)](https://github.com/jomardyan/TubeTracks)

</div>
