#!/usr/bin/env python3
"""
Enhanced YouTube to MP3 Downloader
Download audio from YouTube videos, playlists, and batch files with quality options
Features: Rich error handling, retries, validation, config file, archive, and detailed reporting
Plugin system for multi-platform support (YouTube, TikTok, Instagram, Spotify, SoundCloud, etc.)
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
__version__ = "1.0.0"


def _configure_stdio_for_unicode() -> None:
    """Best-effort: avoid UnicodeEncode/Decode errors on Windows.

    When output is redirected/captured, the parent process often decodes
    using the system code page (e.g., cp1250/cp1252). For maximum
    compatibility, keep the stream encoding but force `errors='replace'`
    so Unicode symbols never crash the process.
    """

    preferred = locale.getpreferredencoding(False)

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue

        encoding = getattr(stream, "encoding", None) or preferred

        try:
            stream.reconfigure(encoding=encoding, errors="replace")
            continue
        except Exception:
            pass

        try:
            buffer = getattr(stream, "buffer", None)
            if buffer is None:
                continue
            wrapped = io.TextIOWrapper(buffer, encoding=encoding, errors="replace")
            setattr(sys, stream_name, wrapped)
        except Exception:
            pass


# ============================================================================
# PLUGIN SYSTEM HELPER FUNCTIONS
# ============================================================================


def get_converter_for_url(url: str) -> Optional[Tuple[str, BaseConverter]]:
    """
    Find the appropriate converter plugin for a given URL.

    Args:
        url: The content URL

    Returns:
        tuple: (plugin_id, converter_instance) or None
    """
    if not PLUGINS_AVAILABLE:
        return None

    try:
        registry = get_global_registry()
        result = registry.find_plugin_for_url(url)
        return result
    except Exception as e:
        if not console:
            return None
        return None


def list_supported_platforms() -> Dict[str, Dict[str, Any]]:
    """
    List all supported platforms and their capabilities.

    Returns:
        dict: Platform information indexed by plugin ID
    """
    if not PLUGINS_AVAILABLE:
        return {}

    try:
        registry = get_global_registry()
        plugins = registry.list_plugins()

        result = {}
        for plugin_id, capabilities in plugins.items():
            result[plugin_id] = {
                "name": capabilities.name,
                "platform": capabilities.platform,
                "description": capabilities.description,
                "supports_playlist": capabilities.supports_playlist,
                "supports_auth": capabilities.supports_auth,
                "supported_content_types": [
                    ct.value for ct in capabilities.supported_content_types
                ],
                "output_formats": capabilities.output_formats,
                "url_patterns": capabilities.url_patterns,
            }
        return result
    except Exception:
        return {}


# Default config file locations
CONFIG_LOCATIONS = [
    Path.home() / ".ytdownloader.conf",
    Path.home() / ".config" / "ytdownloader" / "config.conf",
    Path(".ytdownloader.conf"),
]

# Default archive file location
DEFAULT_ARCHIVE_FILE = Path.home() / ".ytdownloader_archive.txt"

# Exit codes
EXIT_SUCCESS = 0
EXIT_PARTIAL_FAILURE = 1
EXIT_VALIDATION_ERROR = 2
EXIT_ALL_FAILED = 3


@dataclass
class Config:
    """Configuration settings with defaults"""

    quality: str = "medium"
    format: str = "mp3"
    output: str = "./downloads"
    template: str = "%(title)s.%(ext)s"
    embed_metadata: bool = True
    embed_thumbnail: bool = True
    retries: int = 3
    archive_file: Optional[str] = None
    use_archive: bool = True
    proxy: Optional[str] = None
    rate_limit: Optional[str] = None
    cookies_file: Optional[str] = None
    log_file: Optional[str] = None

    @classmethod
    def from_file(cls, config_path: Path) -> "Config":
        """Load config from a .conf file"""
        # Use RawConfigParser to avoid interpolation issues with %(title)s template
        parser = RawConfigParser()
        parser.read(config_path)

        config = cls()

        if "download" in parser:
            section = parser["download"]
            config.quality = section.get("quality", config.quality)
            config.format = section.get("format", config.format)
            config.output = section.get("output", config.output)
            config.template = section.get("template", config.template)
            config.embed_metadata = section.getboolean(
                "embed_metadata", config.embed_metadata
            )
            config.embed_thumbnail = section.getboolean(
                "embed_thumbnail", config.embed_thumbnail
            )
            config.retries = section.getint("retries", config.retries)

        if "archive" in parser:
            section = parser["archive"]
            config.archive_file = section.get("archive_file", config.archive_file)
            config.use_archive = section.getboolean("use_archive", config.use_archive)

        if "network" in parser:
            section = parser["network"]
            config.proxy = section.get("proxy", config.proxy)
            config.rate_limit = section.get("rate_limit", config.rate_limit)
            config.cookies_file = section.get("cookies_file", config.cookies_file)

        if "logging" in parser:
            section = parser["logging"]
            config.log_file = section.get("log_file", config.log_file)

        return config

    def save_to_file(self, config_path: Path):
        """Save current config to a file"""
        # Use RawConfigParser to avoid interpolation issues with %(title)s template
        parser = RawConfigParser()

        parser["download"] = {
            "quality": self.quality,
            "format": self.format,
            "output": self.output,
            "template": self.template,
            "embed_metadata": str(self.embed_metadata).lower(),
            "embed_thumbnail": str(self.embed_thumbnail).lower(),
            "retries": str(self.retries),
        }

        parser["archive"] = {
            "use_archive": str(self.use_archive).lower(),
        }
        if self.archive_file:
            parser["archive"]["archive_file"] = self.archive_file

        parser["network"] = {}
        if self.proxy:
            parser["network"]["proxy"] = self.proxy
        if self.rate_limit:
            parser["network"]["rate_limit"] = self.rate_limit
        if self.cookies_file:
            parser["network"]["cookies_file"] = self.cookies_file

        if self.log_file:
            parser["logging"] = {"log_file": self.log_file}

        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            parser.write(f)


def load_config() -> Config:
    """Load config from the first available config file, or return defaults"""
    for config_path in CONFIG_LOCATIONS:
        if config_path.exists():
            try:
                return Config.from_file(config_path)
            except Exception as e:
                console.print(
                    f"[yellow]Warning:[/yellow] Failed to load config from {config_path}: {e}"
                )
    return Config()


def setup_logging(log_file: Optional[str], quiet: bool = False):
    """Setup logging to file if specified"""
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        if not quiet:
            console.print(f"[dim]Logging to: {log_file}[/dim]")
    else:
        logging.basicConfig(level=logging.WARNING)


def log_download_result(result: "DownloadResult"):
    """Log a download result"""
    if result.success:
        logging.info(
            f"SUCCESS: {result.url} -> {result.output_path} ({result.duration_seconds:.1f}s)"
        )
    else:
        logging.error(
            f"FAILED: {result.url} - {result.error_code.value}: {result.error_message}"
        )


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing/replacing unsafe characters"""
    # Remove or replace unsafe characters
    unsafe_chars = '<>:"/\\|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, "_")

    # Remove control characters
    filename = "".join(c for c in filename if ord(c) >= 32)

    # Trim whitespace and dots from ends
    filename = filename.strip(". ")

    # Limit length (leaving room for extension)
    if len(filename) > 200:
        filename = filename[:200]

    return filename or "untitled"


def clean_youtube_url(url: str, force_single_video: bool = True) -> str:
    """Clean YouTube URL by removing problematic playlist parameters.

    Args:
        url: YouTube URL to clean
        force_single_video: If True, remove auto-generated mix/radio playlist parameters

    Returns:
        Cleaned URL
    """
    if not url or "youtube.com" not in url.lower() and "youtu.be" not in url.lower():
        return url

    try:
        from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

        parsed = urlparse(url)
        params = parse_qs(parsed.query)

        # Remove problematic parameters for single video downloads
        if force_single_video:
            # Remove auto-generated mix/radio parameters
            list_param = params.get("list", [""])[0]
            if list_param.startswith(
                ("RDQM", "RDMM", "RDAO", "RDCLAK", "RDEM", "RDAMVM", "RDCMUC")
            ):
                params.pop("list", None)
                params.pop("start_radio", None)
                params.pop("rv", None)

        # Rebuild URL
        new_query = urlencode(params, doseq=True)
        cleaned = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )

        return cleaned
    except Exception:
        # If URL parsing fails, return original
        return url


def check_file_exists(
    output_dir: str, title: str, audio_format: str, filename_template: str
) -> Optional[str]:
    """Check if a file with the given title already exists in output directory.

    Args:
        output_dir: Output directory path
        title: Video title
        audio_format: Audio format extension
        filename_template: Filename template

    Returns:
        Path to existing file if found, None otherwise
    """
    try:
        safe_title = sanitize_filename(title)

        # Build expected filename from template
        template_vars = {
            "title": safe_title,
            "ext": audio_format,
        }

        expected_name = filename_template
        for key, value in template_vars.items():
            expected_name = expected_name.replace(f"%({key})s", str(value))

        expected_path = Path(output_dir) / expected_name

        if expected_path.exists() and expected_path.stat().st_size > 0:
            return str(expected_path)

        return None
    except Exception:
        return None


class ErrorCode(Enum):
    """Error classification codes"""

    SUCCESS = "success"
    CANCELLED = "cancelled"
    NETWORK_ERROR = "network_error"
    EXTRACTION_ERROR = "extraction_error"
    POSTPROCESS_ERROR = "postprocess_error"
    VALIDATION_ERROR = "validation_error"
    PERMISSION_ERROR = "permission_error"
    NOT_FOUND = "not_found"
    AGE_RESTRICTED = "age_restricted"
    FFMPEG_ERROR = "ffmpeg_error"
    UNKNOWN_ERROR = "unknown_error"


# Human-readable error messages
ERROR_MESSAGES = {
    ErrorCode.SUCCESS: "Download completed successfully",
    ErrorCode.CANCELLED: "Download cancelled",
    ErrorCode.NETWORK_ERROR: "Network error - check your internet connection",
    ErrorCode.EXTRACTION_ERROR: "Failed to extract video information",
    ErrorCode.POSTPROCESS_ERROR: "Error during audio conversion",
    ErrorCode.VALIDATION_ERROR: "Invalid input provided",
    ErrorCode.PERMISSION_ERROR: "Permission denied - check write access",
    ErrorCode.NOT_FOUND: "Video not found or unavailable",
    ErrorCode.AGE_RESTRICTED: "Age-restricted content - authentication required",
    ErrorCode.FFMPEG_ERROR: "FFmpeg error - ensure ffmpeg is installed",
    ErrorCode.UNKNOWN_ERROR: "An unexpected error occurred",
}


class DownloadCancelledError(Exception):
    """Raised to cancel an in-progress download (used by GUI/callback clients)."""


@dataclass
class DownloadResult:
    """Structured result from a download operation"""

    success: bool
    url: str
    output_path: Optional[str] = None
    title: Optional[str] = None
    error_code: ErrorCode = ErrorCode.SUCCESS
    error_message: str = ""
    exception: Optional[Exception] = None
    attempts: int = 1
    duration_seconds: float = 0.0
    skipped: bool = False  # True if skipped due to archive

    def __str__(self) -> str:
        if self.skipped:
            return f"⊘ {self.title or self.url} (already downloaded)"
        if self.success:
            return f"✓ {self.title or self.url}"
        return f"✗ {self.title or self.url}: {self.error_message}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "success": self.success,
            "url": self.url,
            "output_path": self.output_path,
            "title": self.title,
            "error_code": self.error_code.value,
            "error_message": self.error_message,
            "attempts": self.attempts,
            "duration_seconds": self.duration_seconds,
            "skipped": self.skipped,
        }


def classify_error(exception: Exception) -> Tuple[ErrorCode, str]:
    """
    Classify an exception into an ErrorCode with a human-readable message.

    Args:
        exception: The exception to classify

    Returns:
        tuple: (ErrorCode, detailed message)
    """
    error_str = str(exception).lower()

    if isinstance(exception, DownloadCancelledError):
        return ErrorCode.CANCELLED, "Cancelled by user"

    # Check for specific yt-dlp exceptions
    if isinstance(exception, PostProcessingError):
        if "ffmpeg" in error_str or "ffprobe" in error_str:
            return ErrorCode.FFMPEG_ERROR, f"FFmpeg processing failed: {exception}"
        return ErrorCode.POSTPROCESS_ERROR, f"Post-processing failed: {exception}"

    if isinstance(exception, ExtractorError):
        if "not found" in error_str or "404" in error_str:
            return ErrorCode.NOT_FOUND, f"Video not found: {exception}"
        if "age" in error_str or "sign in" in error_str:
            return ErrorCode.AGE_RESTRICTED, f"Age-restricted content: {exception}"
        if "private" in error_str:
            return ErrorCode.NOT_FOUND, f"Video is private: {exception}"
        return ErrorCode.EXTRACTION_ERROR, f"Extraction failed: {exception}"

    if isinstance(exception, DownloadError):
        if (
            "urlopen" in error_str
            or "connection" in error_str
            or "timeout" in error_str
        ):
            return ErrorCode.NETWORK_ERROR, f"Network error: {exception}"
        if "not found" in error_str or "unavailable" in error_str:
            return ErrorCode.NOT_FOUND, f"Video unavailable: {exception}"
        return ErrorCode.EXTRACTION_ERROR, f"Download error: {exception}"

    if isinstance(exception, PermissionError):
        return ErrorCode.PERMISSION_ERROR, f"Permission denied: {exception}"

    if isinstance(exception, FileNotFoundError):
        if "ffmpeg" in error_str or "ffprobe" in error_str:
            return ErrorCode.FFMPEG_ERROR, "FFmpeg not found - please install ffmpeg"
        return ErrorCode.NOT_FOUND, f"File not found: {exception}"

    # Network-related errors
    if any(
        kw in error_str
        for kw in ["timeout", "connection", "network", "urlopen", "socket"]
    ):
        return ErrorCode.NETWORK_ERROR, f"Network error: {exception}"

    # FFmpeg errors
    if "ffmpeg" in error_str or "ffprobe" in error_str:
        return ErrorCode.FFMPEG_ERROR, f"FFmpeg error: {exception}"

    return ErrorCode.UNKNOWN_ERROR, f"Unexpected error: {exception}"


def validate_url(url: str) -> Tuple[bool, str]:
    """
    Validate a URL format against registered platform plugins.
    Falls back to YouTube patterns if plugins not available.

    Args:
        url: The URL to validate

    Returns:
        tuple: (is_valid, error_message)
    """
    if not url:
        return False, "URL cannot be empty"

    # Try plugin system first
    if PLUGINS_AVAILABLE:
        plugin_result = get_converter_for_url(url)
        if plugin_result:
            plugin_id, converter = plugin_result
            return converter.validate_url(url)

    # Fallback to YouTube patterns for backwards compatibility
    youtube_patterns = [
        r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
        r"^https?://(www\.)?youtube\.com/playlist\?list=[\w-]+",
        r"^https?://youtu\.be/[\w-]+",
        r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
        r"^https?://music\.youtube\.com/watch\?v=[\w-]+",
    ]

    for pattern in youtube_patterns:
        if re.match(pattern, url, re.IGNORECASE):
            return True, ""

    error_msg = "Unsupported URL format. "
    if PLUGINS_AVAILABLE:
        platforms = list_supported_platforms()
        if platforms:
            platform_list = ", ".join([p["platform"] for p in platforms.values()])
            error_msg += f"Supported platforms: {platform_list}"
        else:
            error_msg += "Check your URL format."
    else:
        error_msg += "Only YouTube URLs are supported in this configuration."

    return False, error_msg


def check_ffmpeg() -> Tuple[bool, str]:
    """
    Check if ffmpeg is available on the system.
    On Windows, also checks common installation paths and refreshes PATH.

    Returns:
        tuple: (is_available, error_message)
    """
    # Try direct PATH search first
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return True, f"FFmpeg found: {ffmpeg_path}"

    # Windows-specific: refresh PATH from environment and try again
    if sys.platform == "win32":
        try:
            import subprocess as sp

            result = sp.run(
                ["cmd", "/c", "ffmpeg", "-version"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                return True, "FFmpeg found via cmd refresh"
        except Exception:
            pass

        # Check common Windows installation paths
        common_paths = [
            Path.home() / "AppData" / "Local" / "Microsoft" / "WinGet" / "Packages",
            Path("C:/Program Files/ffmpeg"),
            Path("C:/Program Files (x86)/ffmpeg"),
            Path("C:/ffmpeg"),
        ]

        for base_path in common_paths:
            if base_path.exists():
                # Search for ffmpeg.exe
                try:
                    for item in base_path.rglob("ffmpeg.exe"):
                        return True, f"FFmpeg found: {item}"
                except Exception:
                    pass

    return False, "FFmpeg not found. Please install ffmpeg for audio conversion."


def check_output_dir(output_dir: str) -> Tuple[bool, str]:
    """
    Check if output directory is writable.

    Args:
        output_dir: Path to check

    Returns:
        tuple: (is_writable, error_message)
    """
    path = Path(output_dir)

    try:
        # Create directory if it doesn't exist
        path.mkdir(parents=True, exist_ok=True)

        # Test write access
        test_file = path / ".write_test"
        test_file.touch()
        test_file.unlink()

        return True, ""
    except PermissionError:
        return False, f"No write permission for directory: {output_dir}"
    except Exception as e:
        return False, f"Cannot access directory {output_dir}: {e}"


def run_preflight_checks(
    url: Optional[str], output_dir: str, quiet: bool = False
) -> List[Tuple[str, bool, str]]:
    """
    Run preflight validation checks before downloading.

    Args:
        url: YouTube URL (can be None for batch mode)
        output_dir: Output directory path
        quiet: Suppress output

    Returns:
        list of (check_name, passed, message) tuples
    """
    results = []

    # Check FFmpeg
    ffmpeg_ok, ffmpeg_msg = check_ffmpeg()
    results.append(("FFmpeg", ffmpeg_ok, ffmpeg_msg))

    # Check output directory
    dir_ok, dir_msg = check_output_dir(output_dir)
    results.append(
        ("Output Directory", dir_ok, dir_msg if dir_msg else f"Writable: {output_dir}")
    )

    # Check URL if provided
    if url:
        url_ok, url_msg = validate_url(url)
        results.append(
            ("URL Format", url_ok, url_msg if url_msg else "Valid YouTube URL")
        )

    if not quiet:
        # Display preflight results
        table = Table(
            title="Preflight Checks", show_header=True, header_style="bold cyan"
        )
        table.add_column("Check", style="cyan")
        table.add_column("Status", justify="center")
        table.add_column("Details")

        for check_name, passed, message in results:
            status = "[green]✓[/green]" if passed else "[red]✗[/red]"
            msg_style = "" if passed else "red"
            table.add_row(
                check_name,
                status,
                f"[{msg_style}]{message}[/{msg_style}]" if msg_style else message,
            )

        console.print(table)
        console.print()

    return results


def _parse_rate_limit(rate_str: str) -> Optional[int]:
    """
    Parse rate limit string to bytes per second.

    Args:
        rate_str: Rate limit string (e.g., '1M', '500K', '1000')

    Returns:
        int: Bytes per second, or None if invalid
    """
    if not rate_str:
        return None

    rate_str = rate_str.strip().upper()

    multipliers = {
        "K": 1024,
        "M": 1024 * 1024,
        "G": 1024 * 1024 * 1024,
    }

    try:
        if rate_str[-1] in multipliers:
            return int(float(rate_str[:-1]) * multipliers[rate_str[-1]])
        return int(rate_str)
    except (ValueError, IndexError):
        return None


def dry_run_info(
    url: str,
    output_dir: str,
    filename_template: str,
    audio_format: str,
    quality: str,
    is_playlist: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Preview what would be downloaded without actually downloading.

    Args:
        url: YouTube URL
        output_dir: Output directory
        filename_template: Filename template
        audio_format: Audio format
        quality: Quality preset
        is_playlist: Whether to treat as playlist

    Returns:
        dict with video info and resolved paths, or None on error
    """
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": not is_playlist,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            results = []
            entries = info.get("entries", [info]) if "entries" in info else [info]

            for entry in entries:
                if not entry:
                    continue

                # Resolve filename
                title = entry.get("title", "Unknown")
                safe_title = sanitize_filename(title)

                # Build resolved path
                template_vars = {
                    "title": safe_title,
                    "id": entry.get("id", "unknown"),
                    "ext": audio_format,
                    "uploader": sanitize_filename(entry.get("uploader", "Unknown")),
                    "upload_date": entry.get("upload_date", "unknown"),
                    "artist": sanitize_filename(
                        entry.get("artist", entry.get("uploader", "Unknown"))
                    ),
                }

                # Simple template resolution
                resolved_name = filename_template
                for key, value in template_vars.items():
                    resolved_name = resolved_name.replace(f"%({key})s", str(value))

                resolved_path = Path(output_dir) / resolved_name

                results.append(
                    {
                        "title": title,
                        "id": entry.get("id"),
                        "duration": entry.get("duration"),
                        "uploader": entry.get("uploader"),
                        "resolved_path": str(resolved_path),
                        "url": entry.get("webpage_url", url),
                    }
                )

            return {
                "playlist_title": info.get("title") if "entries" in info else None,
                "video_count": len(results),
                "videos": results,
                "quality": quality,
                "format": audio_format,
                "output_dir": output_dir,
            }

    except Exception as e:
        console.print(f"[red]Error extracting info:[/red] {e}")
        return None


def print_dry_run_info(info: Dict[str, Any]):
    """Print dry run information in a formatted table"""
    console.print("\n[bold cyan]═══ Dry Run Preview ═══[/bold cyan]\n")

    if info.get("playlist_title"):
        console.print(f"[bold]Playlist:[/bold] {info['playlist_title']}")

    console.print(f"[bold]Videos:[/bold] {info['video_count']}")
    console.print(f"[bold]Quality:[/bold] {info['quality']}")
    console.print(f"[bold]Format:[/bold] {info['format']}")
    console.print(f"[bold]Output:[/bold] {info['output_dir']}\n")

    table = Table(title="Files to Download", show_header=True, header_style="bold cyan")
    table.add_column("#", style="dim", width=4)
    table.add_column("Title", max_width=40)
    table.add_column("Duration", justify="right")
    table.add_column("Output Path", max_width=50)

    for idx, video in enumerate(info["videos"], 1):
        duration = video.get("duration")
        duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
        table.add_row(
            str(idx),
            video["title"][:40] + ("..." if len(video["title"]) > 40 else ""),
            duration_str,
            video["resolved_path"],
        )

    console.print(table)
    console.print("\n[dim]No files were downloaded (dry run mode)[/dim]\n")


# Quality presets
QUALITY_PRESETS = {
    "low": "128",
    "medium": "192",
    "high": "320",
    "best": "0",  # 0 means best available
}

# Supported audio formats
SUPPORTED_FORMATS = ["mp3", "m4a", "flac", "wav", "ogg"]


class DownloadProgress:
    """Custom progress tracker for downloads with error capture"""

    def __init__(
        self,
        quiet: bool = False,
        progress_callback: Optional["ProgressCallback"] = None,
        cancel_event: Optional["CancelEvent"] = None,
    ):
        self.progress: Optional[Progress] = None
        self.task: Optional[Any] = None
        self.current_file = ""
        self.current_stage = "initializing"
        self.quiet = quiet
        self.last_error: Optional[str] = None
        self.downloaded_file: Optional[str] = None
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event

    def hook(self, d: Dict[str, Any]):
        """Progress hook for yt-dlp"""
        if (
            self.cancel_event is not None
            and getattr(self.cancel_event, "is_set", lambda: False)()
        ):
            raise DownloadCancelledError()

        if d["status"] == "downloading":
            self.current_stage = "downloading"
            if not self.progress and not self.quiet:
                progress = Progress(
                    TextColumn("[bold blue]{task.description}"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                )
                progress.start()
                self.task = progress.add_task(
                    f"[cyan]⬇ Downloading audio stream...", total=100
                )
                self.progress = progress

            if self.progress and ("total_bytes" in d or "total_bytes_estimate" in d):
                total = d.get("total_bytes") or d.get("total_bytes_estimate", 0)
                downloaded = d.get("downloaded_bytes", 0)
                if total > 0:
                    percentage = (downloaded / total) * 100
                    self.progress.update(self.task, completed=percentage)

            if self.progress_callback is not None:
                total = d.get("total_bytes") or d.get("total_bytes_estimate")
                downloaded = d.get("downloaded_bytes")
                speed = d.get("speed")
                eta = d.get("eta")
                filename = d.get("filename")
                try:
                    self.progress_callback(
                        {
                            "status": "downloading",
                            "stage": "downloading",
                            "downloaded_bytes": downloaded,
                            "total_bytes": total,
                            "speed": speed,
                            "eta": eta,
                            "filename": filename,
                        }
                    )
                except Exception:
                    # Never allow UI callback failures to break downloads
                    pass

        elif d["status"] == "finished":
            self.current_stage = "downloaded"
            if self.progress:
                self.progress.update(self.task, completed=100)
                self.progress.stop()
                self.progress = None
            self.downloaded_file = d.get("filename", "file")
            if not self.quiet:
                console.print(f"[green]✓[/green] Download complete")

            if self.progress_callback is not None:
                try:
                    self.progress_callback(
                        {
                            "status": "finished",
                            "stage": "downloaded",
                            "filename": self.downloaded_file,
                        }
                    )
                except Exception:
                    pass

        elif d["status"] == "error":
            if self.progress:
                self.progress.stop()
                self.progress = None
            self.last_error = d.get("error", "Unknown error during download")
            if not self.quiet:
                console.print(f"[red]✗[/red] Error during download: {self.last_error}")

            if self.progress_callback is not None:
                try:
                    self.progress_callback(
                        {
                            "status": "error",
                            "stage": "error",
                            "error": self.last_error,
                        }
                    )
                except Exception:
                    pass

    def cleanup(self):
        """Clean up progress display if still active"""
        if self.progress:
            try:
                self.progress.stop()
            except Exception:
                pass
            self.progress = None


class CancelEvent:
    """Protocol-like helper for typing; any object with is_set() -> bool works."""

    def is_set(self) -> bool:  # pragma: no cover
        raise NotImplementedError


class ProgressCallback:
    """Protocol-like helper for typing; called with a dict payload."""

    def __call__(self, payload: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def cleanup(self):
        """Clean up progress display if still active"""
        if self.progress:
            try:
                self.progress.stop()
            except Exception:
                pass
            self.progress = None


def _download_single_from_playlist(
    entry: Dict[str, Any],
    index: int,
    total: int,
    output_dir: str,
    quality: str,
    audio_format: str,
    embed_metadata: bool,
    embed_thumbnail: bool,
    filename_template: str,
    max_retries: int,
    archive_file: Optional[str],
    proxy: Optional[str],
    rate_limit: Optional[str],
    cookies_file: Optional[str],
    skip_existing: bool,
) -> DownloadResult:
    """Download a single entry from a playlist."""
    video_url = entry.get("webpage_url") or entry.get("url")
    video_title = entry.get("title", "Unknown")
    video_id = entry.get("id", "unknown")

    # Check if file already exists
    if skip_existing:
        existing = check_file_exists(
            output_dir, video_title, audio_format, filename_template
        )
        if existing:
            return DownloadResult(
                success=True,
                url=video_url,
                title=video_title,
                output_path=existing,
                error_code=ErrorCode.SUCCESS,
                skipped=True,
                attempts=0,
                duration_seconds=0.0,
            )

    # Download the video
    return download_audio(
        url=video_url,
        output_dir=output_dir,
        quality=quality,
        audio_format=audio_format,
        embed_metadata=embed_metadata,
        embed_thumbnail=embed_thumbnail,
        filename_template=filename_template,
        quiet=True,  # Suppress individual output
        is_playlist=False,
        max_retries=max_retries,
        archive_file=archive_file,
        proxy=proxy,
        rate_limit=rate_limit,
        cookies_file=cookies_file,
        concurrent_downloads=1,
        skip_existing=False,  # Already checked above
    )


def _download_playlist(
    entries: List[Dict[str, Any]],
    output_dir: str,
    quality: str,
    audio_format: str,
    embed_metadata: bool,
    embed_thumbnail: bool,
    filename_template: str,
    quiet: bool,
    max_retries: int,
    archive_file: Optional[str],
    proxy: Optional[str],
    rate_limit: Optional[str],
    cookies_file: Optional[str],
    progress_callback: Optional[ProgressCallback],
    cancel_event: Optional[CancelEvent],
    concurrent_downloads: int,
    skip_existing: bool,
    playlist_progress_callback: Optional[Callable[[int, int, str], None]],
    playlist_title: str,
    start_time: float,
) -> DownloadResult:
    """Download all entries from a playlist with concurrent processing."""
    total = len(entries)
    results = []
    successful = 0
    skipped = 0
    failed = 0

    if not quiet:
        console.print(f"[cyan]⚙ Concurrent downloads:[/cyan] {concurrent_downloads}")
        console.print(
            f"[cyan]⚙ Skip existing:[/cyan] {'Yes' if skip_existing else 'No'}\\n"
        )

    # Use ThreadPoolExecutor for concurrent downloads
    with ThreadPoolExecutor(max_workers=concurrent_downloads) as executor:
        # Submit all tasks
        future_to_entry = {}
        for idx, entry in enumerate(entries, 1):
            if cancel_event and cancel_event.is_set():
                break

            future = executor.submit(
                _download_single_from_playlist,
                entry=entry,
                index=idx,
                total=total,
                output_dir=output_dir,
                quality=quality,
                audio_format=audio_format,
                embed_metadata=embed_metadata,
                embed_thumbnail=embed_thumbnail,
                filename_template=filename_template,
                max_retries=max_retries,
                archive_file=archive_file,
                proxy=proxy,
                rate_limit=rate_limit,
                cookies_file=cookies_file,
                skip_existing=skip_existing,
            )
            future_to_entry[future] = (idx, entry)

        # Process completed downloads
        for future in as_completed(future_to_entry):
            if cancel_event and cancel_event.is_set():
                break

            idx, entry = future_to_entry[future]
            try:
                result = future.result()
                results.append(result)

                if result.success:
                    if result.skipped:
                        skipped += 1
                        if not quiet:
                            console.print(
                                f"[yellow]⊘[/yellow] [{idx}/{total}] {result.title} [dim](skipped - already exists)[/dim]"
                            )
                    else:
                        successful += 1
                        if not quiet:
                            console.print(
                                f"[green]✓[/green] [{idx}/{total}] {result.title}"
                            )
                else:
                    failed += 1
                    if not quiet:
                        console.print(
                            f"[red]✗[/red] [{idx}/{total}] {result.title}: {result.error_message}"
                        )

                # Update playlist progress
                if playlist_progress_callback:
                    try:
                        playlist_progress_callback(
                            len(results), total, result.title or "Unknown"
                        )
                    except Exception:
                        pass

                # Send progress update
                if progress_callback:
                    try:
                        progress_callback(
                            {
                                "status": "playlist_progress",
                                "current": len(results),
                                "total": total,
                                "successful": successful,
                                "skipped": skipped,
                                "failed": failed,
                                "title": result.title,
                            }
                        )
                    except Exception:
                        pass

            except Exception as e:
                failed += 1
                error_title = entry.get("title", "Unknown")
                if not quiet:
                    console.print(
                        f"[red]✗[/red] [{idx}/{total}] {error_title}: {str(e)}"
                    )

    # Summary
    duration = time.time() - start_time

    if not quiet:
        console.print(f"\\n[bold cyan]═══ Playlist Summary ═══[/bold cyan]")
        console.print(f"[green]✓ Successful:[/green] {successful}")
        if skipped > 0:
            console.print(f"[yellow]⊘ Skipped:[/yellow] {skipped}")
        if failed > 0:
            console.print(f"[red]✗ Failed:[/red] {failed}")
        console.print(f"[cyan]⏱ Total time:[/cyan] {duration:.1f}s\\n")

    # Return result for the playlist as a whole
    return DownloadResult(
        success=(successful + skipped) > 0,
        url=f"playlist:{playlist_title}",
        title=f"{playlist_title} ({successful + skipped}/{total})",
        output_path=output_dir,
        error_code=ErrorCode.SUCCESS if failed == 0 else ErrorCode.UNKNOWN_ERROR,
        error_message=f"{failed} videos failed" if failed > 0 else "",
        attempts=1,
        duration_seconds=duration,
    )


def download_audio(
    url: str,
    output_dir: str = "./downloads",
    quality: str = "medium",
    audio_format: str = "mp3",
    embed_metadata: bool = True,
    embed_thumbnail: bool = True,
    filename_template: str = "%(title)s.%(ext)s",
    quiet: bool = False,
    is_playlist: bool = False,
    max_retries: int = 3,
    retry_delay: float = 2.0,
    archive_file: Optional[str] = None,
    proxy: Optional[str] = None,
    rate_limit: Optional[str] = None,
    cookies_file: Optional[str] = None,
    progress_callback: Optional[ProgressCallback] = None,
    cancel_event: Optional[CancelEvent] = None,
    concurrent_downloads: int = 1,
    skip_existing: bool = True,
    playlist_progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> DownloadResult:
    """
    Download audio from a YouTube video or playlist with retry support.

    Args:
        url: YouTube video or playlist URL
        output_dir: Directory to save the audio file
        quality: Quality preset (low, medium, high, best)
        audio_format: Output audio format
        embed_metadata: Whether to embed metadata
        embed_thumbnail: Whether to embed thumbnail as album art
        filename_template: Template for output filename
        quiet: Suppress output
        is_playlist: Whether to download entire playlist
        max_retries: Maximum number of retry attempts for transient errors
        retry_delay: Base delay between retries (doubles each attempt)
        archive_file: Path to archive file for tracking downloads
        proxy: Proxy URL (e.g., socks5://127.0.0.1:1080)
        rate_limit: Download rate limit (e.g., 1M, 500K)
        cookies_file: Path to cookies file for authentication
        progress_callback: Callback for progress updates
        cancel_event: Event to check for cancellation
        concurrent_downloads: Number of concurrent downloads for playlists (1-5)
        skip_existing: Skip files that already exist
        playlist_progress_callback: Callback for playlist progress (current, total, title)

    Returns:
        DownloadResult: Structured result with success/failure details
    """
    start_time = time.time()
    video_title: Optional[str] = None

    # Clean URL if not explicitly downloading playlist
    if not is_playlist:
        original_url = url
        url = clean_youtube_url(url, force_single_video=True)
        if url != original_url and not quiet:
            console.print(
                f"[dim]→ Cleaned URL (removed auto-generated playlist parameters)[/dim]"
            )

    # Get quality bitrate
    bitrate = QUALITY_PRESETS.get(quality, "192")

    # Create output directory
    try:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
    except PermissionError as e:
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.PERMISSION_ERROR,
            error_message=f"Cannot create output directory: {output_dir}",
            exception=e,
            duration_seconds=time.time() - start_time,
        )

    # Configure postprocessors
    postprocessors = [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": audio_format,
            "preferredquality": bitrate,
        }
    ]

    if embed_metadata:
        postprocessors.append({"key": "FFmpegMetadata"})

    if embed_thumbnail:
        postprocessors.extend(
            [
                {"key": "EmbedThumbnail"},
            ]
        )

    # Setup progress tracking
    progress_tracker = DownloadProgress(
        quiet=quiet,
        progress_callback=progress_callback,
        cancel_event=cancel_event,
    )

    # Configure yt-dlp options
    outtmpl_path = str(Path(output_dir) / filename_template)
    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": postprocessors,
        "outtmpl": outtmpl_path,
        "progress_hooks": [progress_tracker.hook],
        "quiet": True,  # We handle output ourselves
        "no_warnings": quiet,
        "writethumbnail": embed_thumbnail,
        "noplaylist": not is_playlist,
        "continuedl": True,  # Resume partial downloads
        "ignoreerrors": False,
    }

    # Detect and set ffmpeg location if available
    ffmpeg_location = shutil.which("ffmpeg")
    if ffmpeg_location:
        ydl_opts["ffmpeg_location"] = ffmpeg_location
    else:
        # Try common Windows locations
        common_paths = [
            r"C:\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
            r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                ydl_opts["ffmpeg_location"] = path
                break

    # Archive file for tracking completed downloads
    if archive_file:
        ydl_opts["download_archive"] = archive_file

    # Network options
    if proxy:
        ydl_opts["proxy"] = proxy

    if rate_limit:
        ydl_opts["ratelimit"] = _parse_rate_limit(rate_limit)

    if cookies_file:
        if Path(cookies_file).exists():
            ydl_opts["cookiefile"] = cookies_file
        else:
            if not quiet:
                console.print(
                    f"[yellow]Warning:[/yellow] Cookies file not found: {cookies_file}"
                )

    last_exception: Optional[Exception] = None
    last_error_code = ErrorCode.UNKNOWN_ERROR
    last_error_message = ""

    for attempt in range(1, max_retries + 1):
        try:
            if not quiet:
                if attempt == 1:
                    console.print(f"\n[bold cyan]→[/bold cyan] Processing: {url}")
                    console.print(f"  Quality: [yellow]{quality}[/yellow] ({bitrate}k)")
                    console.print(f"  Format: [yellow]{audio_format}[/yellow]")
                    console.print(f"  Output: [yellow]{output_dir}[/yellow]\n")
                else:
                    console.print(
                        f"[yellow]↻[/yellow] Retry attempt {attempt}/{max_retries}..."
                    )

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract info first to show details
                if not quiet:
                    console.print(f"[dim]→ Extracting video information...[/dim]")

                info = ydl.extract_info(url, download=False)

                # Check if info extraction was successful
                if info is None:
                    raise ExtractorError(
                        "Failed to extract video information. Possible reasons:\n"
                        "  • Video is private or members-only\n"
                        "  • Video has been removed\n"
                        "  • Geographic restriction\n"
                        "  • Age-restricted content requiring authentication\n"
                        "Try using the direct video URL without playlist parameters."
                    )

                video_title = info.get("title", "Unknown")

                # Handle playlist with concurrent downloads
                if is_playlist or "entries" in info:
                    entries = info.get("entries", [])
                    valid_entries = [e for e in entries if e is not None]

                    if not valid_entries:
                        raise ExtractorError("No valid videos found in playlist")

                    if not quiet:
                        console.print(
                            f"[bold green]✓ Playlist detected:[/bold green] {info.get('title', 'Unknown')}"
                        )
                        console.print(
                            f"[bold green]📋 Total videos:[/bold green] {len(valid_entries)}\n"
                        )

                    if playlist_progress_callback:
                        try:
                            playlist_progress_callback(
                                0, len(valid_entries), info.get("title", "Unknown")
                            )
                        except Exception:
                            pass

                    # Process playlist entries
                    return _download_playlist(
                        entries=valid_entries,
                        output_dir=output_dir,
                        quality=quality,
                        audio_format=audio_format,
                        embed_metadata=embed_metadata,
                        embed_thumbnail=embed_thumbnail,
                        filename_template=filename_template,
                        quiet=quiet,
                        max_retries=max_retries,
                        archive_file=archive_file,
                        proxy=proxy,
                        rate_limit=rate_limit,
                        cookies_file=cookies_file,
                        progress_callback=progress_callback,
                        cancel_event=cancel_event,
                        concurrent_downloads=max(1, min(5, concurrent_downloads)),
                        skip_existing=skip_existing,
                        playlist_progress_callback=playlist_progress_callback,
                        playlist_title=info.get("title", "Unknown"),
                        start_time=start_time,
                    )

                # Notify about post-processing stages
                if progress_callback is not None:
                    try:
                        progress_callback(
                            {
                                "status": "processing",
                                "stage": "extracting",
                                "message": "Extracting video information",
                            }
                        )
                    except Exception:
                        pass

                # Download
                if not quiet:
                    console.print(f"[dim]→ Starting download...[/dim]")

                ydl.download([url])

                # Post-processing notifications
                if not quiet:
                    console.print(
                        f"[yellow]♪[/yellow] Converting to {audio_format.upper()}..."
                    )

                if progress_callback is not None:
                    try:
                        progress_callback(
                            {
                                "status": "processing",
                                "stage": "converting",
                                "message": f"Converting to {audio_format.upper()}",
                            }
                        )
                    except Exception:
                        pass

                if embed_metadata and not quiet:
                    console.print(f"[dim]→ Embedding metadata...[/dim]")
                if embed_metadata and progress_callback is not None:
                    try:
                        progress_callback(
                            {
                                "status": "processing",
                                "stage": "metadata",
                                "message": "Embedding metadata",
                            }
                        )
                    except Exception:
                        pass

                if embed_thumbnail and not quiet:
                    console.print(f"[dim]→ Embedding thumbnail...[/dim]")
                if embed_thumbnail and progress_callback is not None:
                    try:
                        progress_callback(
                            {
                                "status": "processing",
                                "stage": "thumbnail",
                                "message": "Embedding thumbnail",
                            }
                        )
                    except Exception:
                        pass

                if not quiet:
                    console.print(
                        f"\n[bold green]✓ Download completed successfully![/bold green]\n"
                    )

                return DownloadResult(
                    success=True,
                    url=url,
                    title=video_title,
                    output_path=progress_tracker.downloaded_file,
                    error_code=ErrorCode.SUCCESS,
                    attempts=attempt,
                    duration_seconds=time.time() - start_time,
                )

        except DownloadCancelledError as e:
            progress_tracker.cleanup()
            return DownloadResult(
                success=False,
                url=url,
                title=video_title,
                error_code=ErrorCode.CANCELLED,
                error_message="Cancelled by user",
                exception=e,
                attempts=attempt,
                duration_seconds=time.time() - start_time,
            )

        except (DownloadError, ExtractorError, PostProcessingError) as e:
            progress_tracker.cleanup()
            last_exception = e
            last_error_code, last_error_message = classify_error(e)

            # Only retry on network errors
            if last_error_code == ErrorCode.NETWORK_ERROR and attempt < max_retries:
                delay = retry_delay * (2 ** (attempt - 1))  # Exponential backoff
                if not quiet:
                    console.print(
                        f"[yellow]⚠[/yellow] Network error, retrying in {delay:.1f}s..."
                    )
                time.sleep(delay)
                continue

            # Non-retryable error or max retries reached
            break

        except Exception as e:
            progress_tracker.cleanup()
            last_exception = e
            last_error_code, last_error_message = classify_error(e)
            break

    # All retries failed
    progress_tracker.cleanup()

    if not quiet:
        # Display detailed error
        error_panel = Panel(
            f"[bold]{ERROR_MESSAGES.get(last_error_code, 'Unknown error')}[/bold]\n\n"
            f"[dim]Details:[/dim] {last_error_message}\n"
            f"[dim]URL:[/dim] {url}\n"
            f"[dim]Attempts:[/dim] {attempt}",
            title="[red]Download Failed[/red]",
            border_style="red",
        )
        console.print(error_panel)

    return DownloadResult(
        success=False,
        url=url,
        title=video_title,
        error_code=last_error_code,
        error_message=last_error_message,
        exception=last_exception,
        attempts=attempt,
        duration_seconds=time.time() - start_time,
    )


def download_from_batch_file(
    batch_file: str,
    output_dir: str = "./downloads",
    quality: str = "medium",
    audio_format: str = "mp3",
    embed_metadata: bool = True,
    embed_thumbnail: bool = True,
    filename_template: str = "%(title)s.%(ext)s",
    quiet: bool = False,
    max_retries: int = 3,
    fail_fast: bool = False,
    max_failures: int = 0,
    archive_file: Optional[str] = None,
    proxy: Optional[str] = None,
    rate_limit: Optional[str] = None,
    cookies_file: Optional[str] = None,
    log_file: Optional[str] = None,
) -> Tuple[List[DownloadResult], int]:
    """
    Download audio from multiple URLs in a batch file with detailed reporting.

    Args:
        batch_file: Path to file containing URLs (one per line)
        output_dir: Directory to save files
        quality: Quality preset
        audio_format: Output audio format
        embed_metadata: Whether to embed metadata
        embed_thumbnail: Whether to embed thumbnail
        filename_template: Filename template
        quiet: Suppress output
        max_retries: Max retries per download
        fail_fast: Stop on first failure
        max_failures: Stop after this many failures (0 = no limit)
        archive_file: Path to archive file for tracking downloads
        proxy: Proxy URL
        rate_limit: Download rate limit
        cookies_file: Path to cookies file
        log_file: Path to log file

    Returns:
        tuple: (list of DownloadResult, exit_code)
    """
    results: List[DownloadResult] = []

    # Read batch file
    try:
        with open(batch_file, "r") as f:
            urls = [
                line.strip() for line in f if line.strip() and not line.startswith("#")
            ]
    except FileNotFoundError:
        console.print(
            Panel(
                f"Batch file not found: [bold]{batch_file}[/bold]\n\n"
                "Make sure the file exists and the path is correct.",
                title="[red]File Not Found[/red]",
                border_style="red",
            )
        )
        return results, EXIT_VALIDATION_ERROR
    except PermissionError:
        console.print(
            Panel(
                f"Permission denied reading: [bold]{batch_file}[/bold]",
                title="[red]Permission Error[/red]",
                border_style="red",
            )
        )
        return results, EXIT_VALIDATION_ERROR

    if not urls:
        console.print("[bold yellow]Warning:[/bold yellow] No URLs found in batch file")
        return results, EXIT_SUCCESS

    if not quiet:
        console.print(f"\n[bold cyan]═══ Batch Download Mode ═══[/bold cyan]")
        console.print(f"Found [bold]{len(urls)}[/bold] URL(s) to process\n")

    # Setup logging if specified
    if log_file:
        setup_logging(log_file, quiet)
        logging.info(f"Starting batch download: {len(urls)} URLs")

    failure_count = 0

    for idx, url in enumerate(urls, 1):
        if not quiet:
            console.print(f"[bold]─── Processing {idx}/{len(urls)} ───[/bold]")

        result = download_audio(
            url=url,
            output_dir=output_dir,
            quality=quality,
            audio_format=audio_format,
            embed_metadata=embed_metadata,
            embed_thumbnail=embed_thumbnail,
            filename_template=filename_template,
            quiet=quiet,
            max_retries=max_retries,
            archive_file=archive_file,
            proxy=proxy,
            rate_limit=rate_limit,
            cookies_file=cookies_file,
        )
        results.append(result)

        # Log result
        if log_file:
            log_download_result(result)

        if not result.success:
            failure_count += 1

            if fail_fast:
                if not quiet:
                    console.print("[yellow]Stopping due to --fail-fast flag[/yellow]")
                break

            if max_failures > 0 and failure_count >= max_failures:
                if not quiet:
                    console.print(
                        f"[yellow]Stopping: reached max failures ({max_failures})[/yellow]"
                    )
                break

    # Generate summary
    if not quiet:
        _print_batch_summary(results, urls)

    # Determine exit code
    successful = sum(1 for r in results if r.success)
    failed = len(results) - successful

    if failed == 0:
        return results, EXIT_SUCCESS
    elif successful == 0:
        return results, EXIT_ALL_FAILED
    else:
        return results, EXIT_PARTIAL_FAILURE


def _print_batch_summary(results: List[DownloadResult], all_urls: List[str]):
    """Print a detailed batch download summary table."""
    successful = [r for r in results if r.success]
    failed = [r for r in results if not r.success]

    console.print(
        f"\n[bold cyan]═══════════════════════════════════════════[/bold cyan]"
    )
    console.print(
        f"[bold cyan]           Batch Download Summary           [/bold cyan]"
    )
    console.print(
        f"[bold cyan]═══════════════════════════════════════════[/bold cyan]\n"
    )

    # Summary stats
    total_time = sum(r.duration_seconds for r in results)
    stats_table = Table(show_header=False, box=None)
    stats_table.add_column("Label", style="bold")
    stats_table.add_column("Value")
    stats_table.add_row("Total URLs", str(len(all_urls)))
    stats_table.add_row("Processed", str(len(results)))
    stats_table.add_row("Successful", f"[green]{len(successful)}[/green]")
    stats_table.add_row(
        "Failed", f"[red]{len(failed)}[/red]" if failed else "[green]0[/green]"
    )
    stats_table.add_row("Total Time", f"{total_time:.1f}s")
    console.print(stats_table)

    # Failed downloads details
    if failed:
        console.print(f"\n[bold red]Failed Downloads:[/bold red]")

        fail_table = Table(show_header=True, header_style="bold red")
        fail_table.add_column("#", style="dim", width=4)
        fail_table.add_column("Title/URL", max_width=40)
        fail_table.add_column("Error", max_width=30)
        fail_table.add_column("Attempts", justify="center")

        for idx, result in enumerate(failed, 1):
            display_name = result.title or result.url[:40]
            if len(result.url) > 40 and not result.title:
                display_name += "..."
            error_type = ERROR_MESSAGES.get(result.error_code, "Unknown error")
            fail_table.add_row(str(idx), display_name, error_type, str(result.attempts))

        console.print(fail_table)

    # Success indicator
    if not failed:
        console.print(
            f"\n[bold green]✓ All downloads completed successfully![/bold green]"
        )
    elif successful:
        console.print(
            f"\n[yellow]⚠ Some downloads failed. Check errors above.[/yellow]"
        )
    else:
        console.print(f"\n[bold red]✗ All downloads failed![/bold red]")

    console.print()


def main():
    """Main entry point"""
    _configure_stdio_for_unicode()

    # Load config file defaults
    config = load_config()

    parser = argparse.ArgumentParser(
        description="Enhanced YouTube to MP3 Downloader with config, archive, and network options",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Download single video with default settings
  python downloader.py https://www.youtube.com/watch?v=dQw4w9WgXcQ
  
  # Download with high quality as FLAC
  python downloader.py -q high -f flac https://www.youtube.com/watch?v=VIDEO_ID
  
  # Download entire playlist
  python downloader.py -p https://www.youtube.com/playlist?list=PLAYLIST_ID
  
  # Download from batch file with retries and logging
  python downloader.py -b urls.txt -o ./music -q best --retries 5 --log-file download.log
  
  # Dry run to preview files
  python downloader.py --dry-run https://www.youtube.com/watch?v=VIDEO_ID
  
  # Use proxy and rate limiting
  python downloader.py --proxy socks5://127.0.0.1:1080 --limit-rate 1M URL
  
  # Save current settings to config file
  python downloader.py --save-config
  
  # Skip archive (re-download even if already done)
  python downloader.py --no-archive URL

Exit Codes:
  0 - All downloads successful
  1 - Some downloads failed (partial success)
  2 - Validation/preflight error
  3 - All downloads failed
        """,
    )

    # Positional argument (optional if using batch file)
    parser.add_argument("url", nargs="?", help="YouTube video or playlist URL")

    # Quality and format options
    parser.add_argument(
        "-q",
        "--quality",
        choices=["low", "medium", "high", "best"],
        default=config.quality,
        help=f"Audio quality preset (default: {config.quality})",
    )

    parser.add_argument(
        "-f",
        "--format",
        choices=SUPPORTED_FORMATS,
        default=config.format,
        help=f"Output audio format (default: {config.format})",
    )

    # Output options
    parser.add_argument(
        "-o",
        "--output",
        default=config.output,
        help=f"Output directory (default: {config.output})",
    )

    parser.add_argument(
        "-t",
        "--template",
        default=config.template,
        help="Filename template (default: %%(title)s.%%(ext)s)",
    )

    # Playlist and batch options
    parser.add_argument(
        "-p", "--playlist", action="store_true", help="Download entire playlist"
    )

    parser.add_argument(
        "-b", "--batch-file", help="Download from batch file (one URL per line)"
    )

    # Metadata options
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        default=not config.embed_metadata,
        help="Do not embed metadata",
    )

    parser.add_argument(
        "--no-thumbnail",
        action="store_true",
        default=not config.embed_thumbnail,
        help="Do not embed thumbnail as album art",
    )

    # Error handling options
    parser.add_argument(
        "--retries",
        type=int,
        default=config.retries,
        help=f"Max retry attempts for network errors (default: {config.retries})",
    )

    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="Stop batch processing on first failure",
    )

    parser.add_argument(
        "--max-failures",
        type=int,
        default=0,
        help="Stop batch after N failures (0 = no limit)",
    )

    parser.add_argument(
        "--skip-checks", action="store_true", help="Skip preflight validation checks"
    )

    # Archive options
    parser.add_argument(
        "--archive",
        default=config.archive_file or str(DEFAULT_ARCHIVE_FILE),
        help=f"Archive file to track downloaded videos (default: {DEFAULT_ARCHIVE_FILE})",
    )

    parser.add_argument(
        "--no-archive",
        action="store_true",
        help="Disable archive (re-download even if previously downloaded)",
    )

    # Network options
    parser.add_argument(
        "--proxy",
        default=config.proxy,
        help="Proxy URL (e.g., socks5://127.0.0.1:1080, http://user:pass@host:port)",
    )

    parser.add_argument(
        "--limit-rate",
        default=config.rate_limit,
        help="Download rate limit (e.g., 1M, 500K)",
    )

    parser.add_argument(
        "--cookies",
        default=config.cookies_file,
        help="Path to cookies file for authentication (Netscape format)",
    )

    # Logging options
    parser.add_argument(
        "--log-file", default=config.log_file, help="Log file path for detailed logging"
    )

    # Dry run
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview what would be downloaded without downloading",
    )

    # Config management
    parser.add_argument(
        "--save-config",
        action="store_true",
        help="Save current settings to config file",
    )

    parser.add_argument(
        "--show-config", action="store_true", help="Show current configuration and exit"
    )

    parser.add_argument(
        "--list-plugins",
        action="store_true",
        help="List all available platform plugins and exit",
    )

    # Other options
    parser.add_argument("--quiet", action="store_true", help="Suppress output messages")

    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    # Handle --list-plugins
    if args.list_plugins:
        platforms = list_supported_platforms()
        if not platforms:
            console.print("[yellow]No plugins available[/yellow]")
            sys.exit(EXIT_SUCCESS)

        console.print(
            "\n[bold cyan]═══════════════════════════════════════════[/bold cyan]"
        )
        console.print(
            "[bold cyan]         Supported Platform Plugins          [/bold cyan]"
        )
        console.print(
            "[bold cyan]═══════════════════════════════════════════[/bold cyan]\n"
        )

        for plugin_id, info in platforms.items():
            console.print(f"[bold green]{info['platform']}[/bold green]")
            console.print(f"  Name: [cyan]{info['name']}[/cyan]")
            console.print(f"  Description: {info['description']}")
            console.print(
                f"  Content Types: {', '.join(info['supported_content_types'])}"
            )
            console.print(f"  Formats: {', '.join(info['output_formats'][:3])}...")
            console.print(
                f"  Playlist Support: {'Yes' if info['supports_playlist'] else 'No'}"
            )
            console.print(
                f"  Authentication: {'Required' if info['supports_auth'] else 'Not required'}"
            )
            console.print()

        console.print(f"[dim]Total Plugins: {len(platforms)}[/dim]\n")
        sys.exit(EXIT_SUCCESS)

    # Handle --show-config
    if args.show_config:
        console.print("\n[bold cyan]Current Configuration:[/bold cyan]\n")
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Setting")
        table.add_column("Value")
        table.add_row("Quality", args.quality)
        table.add_row("Format", args.format)
        table.add_row("Output", args.output)
        table.add_row("Template", args.template)
        table.add_row("Retries", str(args.retries))
        table.add_row("Archive", args.archive if not args.no_archive else "(disabled)")
        table.add_row("Proxy", args.proxy or "(none)")
        table.add_row("Rate Limit", args.limit_rate or "(none)")
        table.add_row("Cookies", args.cookies or "(none)")
        table.add_row("Log File", args.log_file or "(none)")
        console.print(table)
        console.print()
        sys.exit(EXIT_SUCCESS)

    # Handle --save-config
    if args.save_config:
        new_config = Config(
            quality=args.quality,
            format=args.format,
            output=args.output,
            template=args.template,
            embed_metadata=not args.no_metadata,
            embed_thumbnail=not args.no_thumbnail,
            retries=args.retries,
            archive_file=args.archive if not args.no_archive else None,
            use_archive=not args.no_archive,
            proxy=args.proxy,
            rate_limit=args.limit_rate,
            cookies_file=args.cookies,
            log_file=args.log_file,
        )
        config_path = CONFIG_LOCATIONS[0]  # Save to home directory
        new_config.save_to_file(config_path)
        console.print(f"[green]✓[/green] Configuration saved to: {config_path}")
        sys.exit(EXIT_SUCCESS)

    # Validate input
    if not args.url and not args.batch_file:
        parser.print_help()
        console.print(
            "\n[bold red]Error:[/bold red] You must provide either a URL or a batch file (-b)"
        )
        sys.exit(EXIT_VALIDATION_ERROR)

    # Setup logging
    if args.log_file:
        setup_logging(args.log_file, args.quiet)

    # Show banner
    if not args.quiet:
        console.print(
            "\n[bold cyan]═══════════════════════════════════════════[/bold cyan]"
        )
        console.print(
            f"[bold cyan]   YouTube MP3 Downloader v{__version__}   [/bold cyan]"
        )
        console.print(
            "[bold cyan]═══════════════════════════════════════════[/bold cyan]\n"
        )

    # Handle dry run
    if args.dry_run:
        if args.batch_file:
            console.print(
                "[yellow]Note:[/yellow] Dry run shows info for first URL in batch file"
            )
            try:
                with open(args.batch_file, "r") as f:
                    urls = [
                        line.strip()
                        for line in f
                        if line.strip() and not line.startswith("#")
                    ]
                if urls:
                    args.url = urls[0]
                else:
                    console.print("[red]No URLs found in batch file[/red]")
                    sys.exit(EXIT_VALIDATION_ERROR)
            except FileNotFoundError:
                console.print(f"[red]Batch file not found: {args.batch_file}[/red]")
                sys.exit(EXIT_VALIDATION_ERROR)

        info = dry_run_info(
            url=args.url,
            output_dir=args.output,
            filename_template=args.template,
            audio_format=args.format,
            quality=args.quality,
            is_playlist=args.playlist,
        )
        if info:
            print_dry_run_info(info)
        sys.exit(EXIT_SUCCESS if info else EXIT_VALIDATION_ERROR)

    # Run preflight checks
    if not args.skip_checks:
        checks = run_preflight_checks(
            url=args.url if not args.batch_file else None,
            output_dir=args.output,
            quiet=args.quiet,
        )

        # Check for critical failures
        critical_checks = ["FFmpeg", "Output Directory"]
        for check_name, passed, message in checks:
            if check_name in critical_checks and not passed:
                console.print(f"[bold red]Cannot proceed:[/bold red] {message}")
                sys.exit(EXIT_VALIDATION_ERROR)

        # URL validation (non-critical for batch mode)
        if args.url and not args.batch_file:
            for check_name, passed, message in checks:
                if check_name == "URL Format" and not passed:
                    console.print(f"[bold red]Cannot proceed:[/bold red] {message}")
                    sys.exit(EXIT_VALIDATION_ERROR)

    # Determine archive file
    archive_file = args.archive if not args.no_archive else None

    # Handle batch file
    if args.batch_file:
        results, exit_code = download_from_batch_file(
            batch_file=args.batch_file,
            output_dir=args.output,
            quality=args.quality,
            audio_format=args.format,
            embed_metadata=not args.no_metadata,
            embed_thumbnail=not args.no_thumbnail,
            filename_template=args.template,
            quiet=args.quiet,
            max_retries=args.retries,
            fail_fast=args.fail_fast,
            max_failures=args.max_failures,
            archive_file=archive_file,
            proxy=args.proxy,
            rate_limit=args.limit_rate,
            cookies_file=args.cookies,
            log_file=args.log_file,
        )
        sys.exit(exit_code)

    # Handle single URL
    result = download_audio(
        url=args.url,
        output_dir=args.output,
        quality=args.quality,
        audio_format=args.format,
        embed_metadata=not args.no_metadata,
        embed_thumbnail=not args.no_thumbnail,
        filename_template=args.template,
        quiet=args.quiet,
        is_playlist=args.playlist,
        max_retries=args.retries,
        archive_file=archive_file,
        proxy=args.proxy,
        rate_limit=args.limit_rate,
        cookies_file=args.cookies,
    )

    # Log result
    if args.log_file:
        log_download_result(result)

    sys.exit(EXIT_SUCCESS if result.success else EXIT_ALL_FAILED)


if __name__ == "__main__":
    main()
