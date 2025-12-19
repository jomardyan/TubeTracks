# AudioDownload-YT

<div align="center">

![Build and Test](https://github.com/jomardyan/AudioDownload-YT/actions/workflows/build.yml/badge.svg)
[![Python 3.8+](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License: GPL v3](https://img.shields.io/badge/license-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

**Multi-platform media downloader with advanced quality control and batch processing capabilities.**

</div>

---

## Overview

AudioDownload-YT is a Python-based media downloader supporting 9+ platforms including YouTube, TikTok, Instagram, SoundCloud, Spotify, and more. Features include multiple quality presets, format conversion, playlist support, and both CLI and GUI interfaces.

## Features

- **Multi-platform support**: YouTube, TikTok, Instagram, SoundCloud, Spotify, Twitch, Dailymotion, Vimeo, Reddit
- **Quality presets**: 128 kbps, 192 kbps, 320 kbps, or original quality
- **Format conversion**: MP3, M4A, FLAC, WAV, OGG via FFmpeg
- **Batch processing**: Download multiple URLs from text files
- **Playlist support**: Automatic playlist extraction and download
- **GUI interface**: User-friendly desktop application with Tkinter
- **Download archive**: Track downloads to prevent duplicates
- **Metadata embedding**: Automatic ID3 tags and thumbnail artwork

## Requirements

- Python 3.8+
- FFmpeg
- Dependencies listed in [requirements.txt](requirements.txt)

---

## Installation

### Quick Install

```bash
git clone https://github.com/jomardyan/AudioDownload-YT.git
cd AudioDownload-YT
make install
```

### Manual Installation

1. **Clone repository**
   ```bash
   git clone https://github.com/jomardyan/AudioDownload-YT.git
   cd AudioDownload-YT
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install FFmpeg**
   You can use the provided cross-platform PowerShell script:
   ```powershell
   pwsh ./install_ffmpeg.ps1
   ```
   Or install manually:
   - **Windows**: `winget install Gyan.FFmpeg`
   - **macOS**: `brew install ffmpeg`
   - **Linux**: `sudo apt-get install ffmpeg`

### Verify Installation

```bash
python --version          # Check Python
ffmpeg -version          # Check FFmpeg
python downloader.py --help  # Test downloader
```

---

## Quick Start

### CLI Usage

```bash
# Single download
python downloader.py "https://www.youtube.com/watch?v=VIDEO_ID"

# With quality and format
python downloader.py -q high -f flac "URL"

# Playlist
python downloader.py -p "PLAYLIST_URL"

# Batch from file
python downloader.py -b urls.txt
```

### GUI

Launch the desktop interface:

```bash
python ytdownloader_gui.py
```

Or with Make:

```bash
make gui
```

---

## Usage

### Quality Options

| Preset | Bitrate | Use Case |
|--------|---------|----------|
| `low` | 128 kbps | Podcasts, audiobooks |
| `medium` | 192 kbps | General listening (default) |
| `high` | 320 kbps | High-quality music |
| `best` | Original | Maximum quality |

### Output Formats

Supported formats: `mp3`, `m4a`, `flac`, `wav`, `ogg`

```bash
python downloader.py -f mp3 <url>
python downloader.py -f flac -q best <url>
```

### Common Options

```bash
# Custom output directory
python downloader.py -o ~/Music <url>

# Custom filename template
python downloader.py -t "%(artist)s - %(title)s" <url>

# Dry-run (preview without downloading)
python downloader.py --dry-run <url>

# Network options
python downloader.py --proxy socks5://127.0.0.1:1080 <url>
python downloader.py --limit-rate 1M <url>

# Error handling
python downloader.py --retries 5 <url>
```

### Configuration

View or save configuration:

```bash
python downloader.py --show-config
python downloader.py --save-config
```

Configuration files are loaded from:
1. `~/.ytdownloader.conf`
2. `./.ytdownloader.conf`

---

## Supported Platforms

| Platform | Playlist | Content Types |
|----------|----------|---------------|
| YouTube | ✅ | Videos, Shorts, Music |
| TikTok | ✅ | Videos, Clips |
| Instagram | ❌ | Posts, Reels, Stories |
| SoundCloud | ✅ | Tracks, Playlists |
| Spotify | ✅ | Tracks, Playlists, Albums |
| Twitch | ❌ | VODs, Clips, Highlights |
| Dailymotion | ✅ | Videos, Playlists |
| Vimeo | ✅ | Videos, Channels |
| Reddit | ❌ | Videos, Posts |

View all plugins: `python downloader.py --list-plugins`

See [PLUGIN_API.md](PLUGIN_API.md) for custom plugin development.

---

## Development

### Testing

```bash
make test              # Run all tests
make smoke-test        # Quick validation
make coverage          # Coverage report
```

### Code Quality

```bash
make lint              # Check code style
make format            # Auto-format code
make check             # Run all checks
```

---

## Disclaimer

This software is provided for educational and personal use only. Users are solely responsible for ensuring their usage complies with applicable laws, regulations, and the terms of service of the platforms from which content is downloaded. The software owner and contributors assume no responsibility or liability for any misuse, legal violations, or consequences arising from the use of this software.

By using this software, you acknowledge that:
- You have the legal right to download the content
- You will respect copyright laws and intellectual property rights
- You will comply with the terms of service of all platforms accessed
- The software owner is not liable for your actions or any resulting damages

## License

This project is licensed under the GNU General Public License v3.0 or later — see LICENSE file for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Acknowledgments

This project uses:
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) — YouTube extraction and download
- [rich](https://github.com/Textualize/rich) — Rich terminal output
- [FFmpeg](https://ffmpeg.org/) — Audio processing and conversion
