#!/usr/bin/env python3
"""TubeTracks: Enhanced YouTube to MP3 Downloader

Download audio from YouTube videos, playlists, and batch files with quality options.
Features: Rich error handling, retries, validation, config file, archive, and detailed reporting.
Plugin system for multi-platform support (YouTube, TikTok, Instagram, Spotify, SoundCloud, etc.).
"""

from __future__ import annotations

import argparse
import io
import json
import locale
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser, RawConfigParser
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError

# Import plugin system
try:
    from plugins import BaseConverter, ContentType, get_global_registry

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False

console = Console()

# Version
__version__ = "1.5.1"

# ============================================================================
# CONSTANTS
# ============================================================================

# Quality presets mapping to bitrate values
QUALITY_PRESETS = {
    "low": "128",
    "medium": "192",
    "high": "320",
    "best": "0",  # 0 = original quality (lossless)
}

# Supported audio/video output formats
SUPPORTED_FORMATS = ["mp3", "m4a", "flac", "wav", "ogg", "opus", "vorbis", "mp4"]

# Default archive file location
DEFAULT_ARCHIVE_FILE = Path.home() / ".ytdownloader_archive.txt"

# Default config file location
DEFAULT_CONFIG_FILE = Path.home() / ".ytdownloader.conf"

# ============================================================================
# ENUMS
# ============================================================================


class ErrorCode(Enum):
    """Error codes for download failures"""

    SUCCESS = 0
    INVALID_URL = 1
    NETWORK_ERROR = 2
    EXTRACTION_ERROR = 3
    DOWNLOAD_ERROR = 4
    POSTPROCESSING_ERROR = 5
    PERMISSION_ERROR = 6
    FFMPEG_ERROR = 7
    FILE_ERROR = 8
    PLUGIN_ERROR = 9
    CONFIGURATION_ERROR = 10
    TIMEOUT_ERROR = 11
    UNKNOWN_ERROR = 99


# ============================================================================
# DATACLASSES
# ============================================================================


@dataclass
class Config:
    """Configuration for downloader"""

    quality: str = "medium"
    format: str = "mp3"
    output: str = "./downloads"
    template: str = "%(title)s.%(ext)s"
    retries: int = 3
    concurrent_downloads: int = 1
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    archive_file: Optional[str] = None
    proxy: Optional[str] = None
    rate_limit: Optional[str] = None
    cookies_file: Optional[str] = None
    log_file: Optional[str] = None
    quiet: bool = False
    dry_run: bool = False

    def save_to_file(self, path: Path) -> None:
        """Save configuration to INI file"""
        config = RawConfigParser()
        config.add_section("download")
        config.set("download", "quality", self.quality)
        config.set("download", "format", self.format)
        config.set("download", "output", self.output)
        config.set("download", "template", self.template)
        config.set("download", "retries", str(self.retries))
        config.set("download", "concurrent_downloads", str(self.concurrent_downloads))
        config.set("download", "embed_metadata", str(self.embed_metadata))
        config.set("download", "embed_thumbnail", str(self.embed_thumbnail))

        config.add_section("network")
        if self.proxy:
            config.set("network", "proxy", self.proxy)
        if self.rate_limit:
            config.set("network", "rate_limit", self.rate_limit)
        if self.cookies_file:
            config.set("network", "cookies_file", self.cookies_file)

        config.add_section("archive")
        if self.archive_file:
            config.set("archive", "archive_file", self.archive_file)

        config.add_section("logging")
        if self.log_file:
            config.set("logging", "log_file", self.log_file)

        with open(path, "w") as f:
            config.write(f)

    @classmethod
    def from_file(cls, path: Path) -> Config:
        """Load configuration from INI file"""
        config = RawConfigParser()
        config.read(path)

        kwargs = {}
        if config.has_section("download"):
            for key in [
                "quality",
                "format",
                "output",
                "template",
                "embed_metadata",
                "embed_thumbnail",
            ]:
                if config.has_option("download", key):
                    value = config.get("download", key)
                    if key in ("embed_metadata", "embed_thumbnail"):
                        value = value.lower() in ("true", "1", "yes")
                    kwargs[key] = value

            if config.has_option("download", "retries"):
                kwargs["retries"] = config.getint("download", "retries")
            if config.has_option("download", "concurrent_downloads"):
                kwargs["concurrent_downloads"] = config.getint(
                    "download", "concurrent_downloads"
                )

        if config.has_section("network"):
            if config.has_option("network", "proxy"):
                kwargs["proxy"] = config.get("network", "proxy")
            if config.has_option("network", "rate_limit"):
                kwargs["rate_limit"] = config.get("network", "rate_limit")
            if config.has_option("network", "cookies_file"):
                kwargs["cookies_file"] = config.get("network", "cookies_file")

        if config.has_section("archive"):
            if config.has_option("archive", "archive_file"):
                kwargs["archive_file"] = config.get("archive", "archive_file")

        if config.has_section("logging"):
            if config.has_option("logging", "log_file"):
                kwargs["log_file"] = config.get("logging", "log_file")

        return cls(**kwargs)


@dataclass
class DownloadResult:
    """Result of a download operation"""

    success: bool
    url: str = ""
    title: str = ""
    output_path: Optional[str] = None
    error_code: ErrorCode = ErrorCode.SUCCESS
    error_message: str = ""
    attempts: int = 1
    duration_seconds: float = 0.0
    file_size: int = 0
    skipped: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "url": self.url,
            "title": self.title,
            "output_path": self.output_path,
            "error_code": self.error_code.name,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "file_size": self.file_size,
            "skipped": self.skipped,
        }

    def __str__(self) -> str:
        if self.skipped:
            return f"⊘ {self.title} - already downloaded"
        elif self.success:
            return f"✓ {self.title}"
        else:
            return f"✗ {self.title} - {self.error_message}"


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


def _parse_rate_limit(limit: Optional[str]) -> Optional[int]:
    """Parse rate limit string (e.g., '500K', '1M', '1G') to bytes per second"""
    if not limit:
        return None

    limit = limit.strip().upper()
    if not limit:
        return None

    multipliers = {"K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024}

    try:
        if limit[-1] in multipliers:
            number = float(limit[:-1])
            return int(number * multipliers[limit[-1]])
        else:
            return int(float(limit))
    except (ValueError, IndexError):
        return None


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to remove unsafe characters"""
    if not filename or filename == "...":
        return "untitled"

    # Remove unsafe characters
    unsafe_chars = r'<>:"/\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "")

    # Limit length
    if len(filename) > 200:
        filename = filename[:200]

    return filename.strip() or "untitled"


def validate_url(url: str) -> Tuple[bool, str]:
    """Validate if URL is supported by any plugin or built-in support"""
    if not url or not url.strip():
        return False, "URL cannot be empty"

    url = url.strip()

    # Check if URL has valid format
    if not url.startswith(("http://", "https://")):
        return False, "URL must start with http:// or https://"

    try:
        if PLUGINS_AVAILABLE:
            registry = get_global_registry()
            result = registry.find_plugin_for_url(url)
            if result:
                return True, ""

        # Fallback: accept common video platforms
        common_patterns = [
            r"youtube\.com",
            r"youtu\.be",
            r"tiktok\.com",
            r"instagram\.com",
            r"soundcloud\.com",
            r"spotify\.com",
            r"twitch\.tv",
            r"vimeo\.com",
            r"dailymotion\.com",
            r"reddit\.com",
        ]

        if any(re.search(pattern, url, re.IGNORECASE) for pattern in common_patterns):
            return True, ""

        return False, f"Unsupported platform: {url}"
    except Exception as e:
        return False, f"Error validating URL: {str(e)}"


def check_ffmpeg() -> Tuple[bool, str]:
    """Check if FFmpeg is available on the system"""
    try:
        if shutil.which("ffmpeg"):
            return True, "FFmpeg found"

        # On Windows, try to refresh PATH and check again
        if sys.platform == "win32":
            try:
                import subprocess

                subprocess.run(
                    "cmd /c ffmpeg -version",
                    capture_output=True,
                    timeout=2,
                    shell=True,
                )
                return True, "FFmpeg found"
            except Exception:
                pass

        return False, "FFmpeg not found. Please install FFmpeg: https://ffmpeg.org"
    except Exception as e:
        return False, f"Error checking FFmpeg: {str(e)}"


def check_output_dir(output_dir: str) -> Tuple[bool, str]:
    """Check if output directory exists or can be created"""
    try:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        return True, "Output directory ready"
    except PermissionError:
        return False, f"Permission denied: {output_dir}"
    except Exception as e:
        return False, f"Cannot create output directory: {str(e)}"


def load_config(config_file: Optional[str] = None) -> Config:
    """Load configuration from file or return defaults"""
    if config_file and Path(config_file).exists():
        try:
            return Config.from_file(Path(config_file))
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to load config: {e}[/yellow]")

    # Try default location
    if DEFAULT_CONFIG_FILE.exists():
        try:
            return Config.from_file(DEFAULT_CONFIG_FILE)
        except Exception:
            pass

    return Config()


def list_supported_platforms() -> Dict[str, Dict[str, Any]]:
    """List all supported platforms from plugins"""
    if not PLUGINS_AVAILABLE:
        return {}

    try:
        registry = get_global_registry()
        platforms = {}
        for plugin_id, caps in registry.list_plugins().items():
            platforms[plugin_id] = {
                "platform": caps.platform,
                "version": caps.version,
                "description": caps.description,
                "supports_playlist": caps.supports_playlist,
            }
        return platforms
    except Exception:
        return {}


def get_converter_for_url(url: str) -> Optional[Tuple[str, BaseConverter]]:
    """Get the converter for a given URL"""
    if not PLUGINS_AVAILABLE:
        return None

    try:
        registry = get_global_registry()
        return registry.find_plugin_for_url(url)
    except Exception:
        return None


class DownloadProgress:
    """Progress tracker for downloads"""

    def __init__(
        self,
        quiet: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
        cancel_event: Optional[Any] = None,
    ):
        self.quiet = quiet
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event

    def hook(self, d: Dict[str, Any]) -> None:
        """Progress hook for yt-dlp"""
        if self.cancel_event and self.cancel_event.is_set():
            raise DownloadError("Download cancelled by user")

        if self.quiet:
            return

        if d["status"] == "downloading":
            info = f"⬇  {d.get('_percent_str', 'N/A')} at {d.get('_speed_str', 'N/A')}"
            if self.progress_callback:
                self.progress_callback(info)

        elif d["status"] == "finished":
            if self.progress_callback:
                self.progress_callback("✓ Download finished")


def download_audio(
    url: str,
    output_dir: str = "./downloads",
    quality: str = "medium",
    audio_format: str = "mp3",
    quiet: bool = False,
    **kwargs,
) -> DownloadResult:
    """
    Download audio from a URL

    Args:
        url: Content URL
        output_dir: Output directory
        quality: Quality preset (low, medium, high, best)
        audio_format: Output format (mp3, m4a, etc.)
        quiet: Suppress output
        **kwargs: Additional options

    Returns:
        DownloadResult with download status
    """
    # Validate inputs
    valid, msg = validate_url(url)
    if not valid:
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.INVALID_URL,
            error_message=msg,
        )

    valid, msg = check_output_dir(output_dir)
    if not valid:
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.PERMISSION_ERROR,
            error_message=msg,
        )

    valid, msg = check_ffmpeg()
    if not valid:
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.FFMPEG_ERROR,
            error_message=msg,
        )

    # Try plugin system first
    if PLUGINS_AVAILABLE:
        try:
            registry = get_global_registry()
            result = registry.find_plugin_for_url(url)
            if result:
                plugin_id, converter = result
                success, file_path, error = converter.download(
                    url, output_dir, quality=quality, format=audio_format, **kwargs
                )
                if success:
                    return DownloadResult(
                        success=True,
                        url=url,
                        title=audio_format,
                        output_path=file_path,
                    )
                else:
                    return DownloadResult(
                        success=False,
                        url=url,
                        error_code=ErrorCode.DOWNLOAD_ERROR,
                        error_message=error or "Download failed",
                    )
        except Exception as e:
            return DownloadResult(
                success=False,
                url=url,
                error_code=ErrorCode.PLUGIN_ERROR,
                error_message=str(e),
            )

    # Fallback to yt-dlp
    return DownloadResult(
        success=False,
        url=url,
        error_code=ErrorCode.PLUGIN_ERROR,
        error_message="No suitable plugin found for URL",
    )


def main() -> int:
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="TubeTracks: Multi-platform media downloader"
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="URL to download",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default="medium",
        choices=list(QUALITY_PRESETS.keys()),
        help="Quality preset (default: medium)",
    )
    parser.add_argument(
        "-f",
        "--format",
        default="mp3",
        choices=SUPPORTED_FORMATS,
        help="Output format (default: mp3)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="./downloads",
        help="Output directory (default: ./downloads)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--show-config",
        action="store_true",
        help="Display current configuration",
    )
    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List available plugins",
    )

    args = parser.parse_args()

    if args.show_config:
        config = load_config()
        console.print(f"[bold]Configuration:[/bold]")
        console.print(f"  Quality: {config.quality}")
        console.print(f"  Format: {config.format}")
        console.print(f"  Output: {config.output}")
        console.print(f"  Retries: {config.retries}")
        return 0

    if args.list_plugins:
        if PLUGINS_AVAILABLE:
            registry = get_global_registry()
            plugins = registry.list_plugins()
            console.print(f"[bold]Total Plugins: {len(plugins)}[/bold]")
            console.print("")
            for plugin_id, caps in plugins.items():
                console.print(f"  • {caps.platform}: {caps.description}")
        else:
            console.print("[yellow]Plugin system not available[/yellow]")
        return 0

    if not args.url:
        parser.print_help()
        return 2

    # Validate URL
    valid, msg = validate_url(args.url)
    if not valid:
        console.print(f"[red]Error: {msg}[/red]")
        return 2

    # Perform download
    result = download_audio(
        args.url,
        output_dir=args.output,
        quality=args.quality,
        audio_format=args.format,
    )

    if result.success:
        console.print(f"[green]{result}[/green]")
        return 0
    else:
        console.print(f"[red]{result}[/red]")
        return 1


if __name__ == "__main__":
    sys.exit(main())