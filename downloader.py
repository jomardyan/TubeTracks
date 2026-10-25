#!/usr/bin/env python3
"""TubeTracks: Enhanced YouTube to MP3 Downloader

Download audio from YouTube videos, playlists, and batch files with quality options.
Features: Rich error handling, retries, validation, config file, archive, and detailed reporting.
Plugin system for multi-platform support (YouTube, TikTok, Instagram, Spotify, SoundCloud, etc.).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from configparser import RawConfigParser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import yt_dlp
from rich.console import Console
from yt_dlp.utils import DownloadError

# Import plugin system
try:
    from plugins import BaseConverter, get_global_registry

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False

console = Console()

# Version
__version__ = "1.6.0"

# ============================================================================
# CONSTANTS
# ============================================================================

# Quality presets mapping to bitrate values
QUALITY_PRESETS = {
    "low": "128",
    "medium": "192",
    "high": "320",
    "best": "0",  # Highest encoder quality; cannot restore source quality
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
    CANCELLED = 12
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
    use_archive: bool = True
    archive_file: str | None = None
    proxy: str | None = None
    rate_limit: str | None = None
    cookies_file: str | None = None
    log_file: str | None = None
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
        config.set("archive", "use_archive", str(self.use_archive))
        if self.archive_file:
            config.set("archive", "archive_file", self.archive_file)

        config.add_section("logging")
        if self.log_file:
            config.set("logging", "log_file", self.log_file)

        with open(path, "w", encoding="utf-8") as f:
            config.write(f)

    @classmethod
    def from_file(cls, path: Path) -> Config:
        """Load configuration from INI file"""
        config = RawConfigParser()
        config.read(path, encoding="utf-8")

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
            if config.has_option("archive", "use_archive"):
                kwargs["use_archive"] = config.getboolean("archive", "use_archive")
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
    output_path: str | None = None
    error_code: ErrorCode = ErrorCode.SUCCESS
    error_message: str = ""
    attempts: int = 1
    duration_seconds: float = 0.0
    file_size: int = 0
    skipped: bool = False

    def to_dict(self) -> dict[str, Any]:
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


def _parse_rate_limit(limit: str | None) -> int | None:
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


ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from strings."""
    return ANSI_ESCAPE.sub("", text or "")


def _classify_error(message: str) -> ErrorCode:
    """Best-effort mapping from error message to ErrorCode."""
    msg = (message or "").lower()

    if "cancelled" in msg or "canceled" in msg:
        return ErrorCode.CANCELLED
    if "ffmpeg" in msg and ("not found" in msg or "missing" in msg):
        return ErrorCode.FFMPEG_ERROR
    if "permission denied" in msg:
        return ErrorCode.PERMISSION_ERROR
    if "http error 403" in msg or "403" in msg or "forbidden" in msg:
        return ErrorCode.PERMISSION_ERROR
    if "http error 429" in msg or "too many requests" in msg:
        return ErrorCode.NETWORK_ERROR
    if "timed out" in msg or "timeout" in msg:
        return ErrorCode.TIMEOUT_ERROR
    if "proxy" in msg or "network" in msg or "connection" in msg:
        return ErrorCode.NETWORK_ERROR
    if "extractor" in msg or "unable to extract" in msg:
        return ErrorCode.EXTRACTION_ERROR
    if "postprocessing" in msg or "post-processing" in msg:
        return ErrorCode.POSTPROCESSING_ERROR
    if "cookie" in msg or "sign in" in msg or "age" in msg:
        return ErrorCode.PERMISSION_ERROR

    return ErrorCode.DOWNLOAD_ERROR


def _is_retryable(error_code: ErrorCode) -> bool:
    """Return True when a retry is likely to help."""
    return error_code in {
        ErrorCode.NETWORK_ERROR,
        ErrorCode.TIMEOUT_ERROR,
        ErrorCode.DOWNLOAD_ERROR,
        ErrorCode.EXTRACTION_ERROR,
    }


def _normalize_progress_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize yt-dlp progress payload for the GUI."""
    status = payload.get("status")
    postprocessor = (payload.get("postprocessor") or "").lower()

    stage = payload.get("stage", "")
    if status == "downloading":
        stage = stage or "downloading"
    elif status == "finished":
        stage = stage or "downloaded"

    if postprocessor:
        if "extractaudio" in postprocessor:
            stage = "converting"
        elif "metadata" in postprocessor:
            stage = "metadata"
        elif "embedthumbnail" in postprocessor or "thumbnail" in postprocessor:
            stage = "thumbnail"
        payload = dict(payload)
        payload["status"] = "processing"
        payload["stage"] = stage
        return payload

    payload = dict(payload)
    if stage:
        payload["stage"] = stage
    return payload


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


def validate_url(url: str) -> tuple[bool, str]:
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


def check_ffmpeg() -> tuple[bool, str]:
    """Check if FFmpeg is available on the system"""
    try:
        if shutil.which("ffmpeg"):
            return True, "FFmpeg found"

        # On Windows, try to refresh PATH and check again
        if sys.platform == "win32":
            try:
                import subprocess

                result = subprocess.run(
                    ["ffmpeg", "-version"],
                    capture_output=True,
                    timeout=2,
                    check=False,
                )
                if result.returncode == 0:
                    return True, "FFmpeg found"
            except Exception:
                pass

        return False, "FFmpeg not found. Please install FFmpeg: https://ffmpeg.org"
    except Exception as e:
        return False, f"Error checking FFmpeg: {str(e)}"


def check_output_dir(output_dir: str) -> tuple[bool, str]:
    """Check if output directory exists or can be created"""
    try:
        output_path = Path(output_dir).expanduser()
        output_path.mkdir(parents=True, exist_ok=True)
        return True, "Output directory ready"
    except PermissionError:
        return False, f"Permission denied: {output_dir}"
    except Exception as e:
        return False, f"Cannot create output directory: {str(e)}"


def load_config(config_file: str | None = None) -> Config:
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


def list_supported_platforms() -> dict[str, dict[str, Any]]:
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


def get_converter_for_url(url: str) -> tuple[str, BaseConverter] | None:
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
        progress_callback: Callable[[str], None] | None = None,
        cancel_event: Any | None = None,
    ):
        self.quiet = quiet
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event

    def hook(self, d: dict[str, Any]) -> None:
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


def dry_run_info(
    url: str,
    output_dir: str = "./downloads",
    filename_template: str = "%(title)s.%(ext)s",
    audio_format: str = "mp3",
    quality: str = "medium",
    is_playlist: bool = False,
    **kwargs,
) -> dict[str, Any] | None:
    """
    Extract metadata without downloading (dry run / preview)

    Args:
        url: Content URL
        output_dir: Output directory (for path resolution)
        filename_template: Output filename template
        audio_format: Output format
        quality: Quality preset
        is_playlist: Whether to treat as playlist

    Returns:
        Dictionary with metadata or None on failure
    """
    try:
        converter = get_converter_for_url(url)
        if converter:
            _, plugin = converter
            info = plugin.get_info(url, is_playlist=is_playlist, **kwargs)
        else:
            from plugins.yt_dlp_converter import network_options

            with yt_dlp.YoutubeDL(
                {
                    "quiet": True,
                    "no_warnings": True,
                    "extract_flat": "in_playlist" if is_playlist else False,
                    "noplaylist": not is_playlist,
                    **network_options(kwargs),
                }
            ) as ydl:
                info = ydl.extract_info(url, download=False)
        if not info:
            return None

        playlist = "entries" in info or info.get("is_playlist", False)
        entries = (
            [entry for entry in info.get("entries") or [] if entry]
            if playlist
            else [info]
        )
        result = dict(info)
        result.update(
            {
                "url": url,
                "output_dir": output_dir,
                "format": audio_format,
                "quality": quality,
                "template": filename_template,
                "is_playlist": playlist,
                "video_count": len(entries),
                "videos": [],
            }
        )
        if playlist:
            result["playlist_title"] = info.get("title", "Unknown Playlist")
        # Let yt-dlp resolve all template fields (artist, id, playlist index, etc.).
        with yt_dlp.YoutubeDL(
            {
                "quiet": True,
                "outtmpl": str(Path(output_dir).expanduser() / filename_template),
            }
        ) as ydl:
            for index, entry in enumerate(entries[:10], 1):
                metadata = dict(entry)
                metadata["ext"] = "ogg" if audio_format == "vorbis" else audio_format
                if playlist:
                    metadata.setdefault("playlist_index", index)
                result["videos"].append(
                    {
                        "title": entry.get("title", "Unknown"),
                        "duration": entry.get("duration"),
                        "uploader": entry.get("uploader"),
                        "url": entry.get("webpage_url") or entry.get("url") or url,
                        "resolved_path": ydl.prepare_filename(metadata),
                    }
                )
        return result
    except Exception as exc:
        console.print(f"[red]Error extracting info: {exc}[/red]")
        return None


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
    url = url.strip()
    output_dir = str(Path(output_dir).expanduser())
    if quality not in QUALITY_PRESETS or audio_format not in SUPPORTED_FORMATS:
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.CONFIGURATION_ERROR,
            error_message=f"Unsupported quality or format: {quality}, {audio_format}",
        )
    cancel_event = kwargs.get("cancel_event")
    if cancel_event and cancel_event.is_set():
        return DownloadResult(
            success=False,
            url=url,
            error_code=ErrorCode.CANCELLED,
            error_message="Download cancelled by user",
            attempts=0,
        )
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

    cancel_event = kwargs.get("cancel_event")
    max_retries = kwargs.get("max_retries")
    retry_delay = kwargs.get("retry_delay", 1.0)
    retry_backoff = kwargs.get("retry_backoff", 1.6)
    progress_callback = kwargs.get("progress_callback")

    if max_retries is not None:
        try:
            max_retries = max(0, int(max_retries))
        except (TypeError, ValueError):
            max_retries = 0
    else:
        max_retries = 0

    def progress_adapter(payload: dict[str, Any]) -> None:
        if cancel_event and cancel_event.is_set():
            raise DownloadError("Download cancelled by user")
        if progress_callback:
            progress_callback(_normalize_progress_payload(payload))

    # Try plugin system first
    if PLUGINS_AVAILABLE:
        start_time = time.monotonic()
        attempts = 0
        try:
            registry = get_global_registry()
            result = registry.find_plugin_for_url(url)
            if result:
                plugin_id, converter = result
                while True:
                    if cancel_event and cancel_event.is_set():
                        return DownloadResult(
                            success=False,
                            url=url,
                            error_code=ErrorCode.CANCELLED,
                            error_message="Download cancelled by user",
                            attempts=attempts,
                        )

                    attempts += 1
                    try:
                        success, file_path, error = converter.download(
                            url,
                            output_dir,
                            quality=quality,
                            format=audio_format,
                            progress_hook=progress_adapter,
                            quiet=quiet,
                            **kwargs,
                        )
                    except Exception as e:
                        success = False
                        file_path = None
                        error = str(e)

                    if success:
                        return DownloadResult(
                            success=True,
                            url=url,
                            title=Path(file_path).stem if file_path else url,
                            output_path=file_path,
                            file_size=Path(file_path).stat().st_size
                            if file_path and Path(file_path).is_file()
                            else 0,
                            attempts=attempts,
                            duration_seconds=time.monotonic() - start_time,
                        )

                    error_message = _strip_ansi(error or "Download failed")
                    error_code = _classify_error(error_message)

                    if "skipped" in error_message.lower():
                        return DownloadResult(
                            success=True,
                            url=url,
                            title=Path(file_path).stem if file_path else url,
                            output_path=file_path,
                            error_code=ErrorCode.SUCCESS,
                            error_message=error_message,
                            attempts=attempts,
                            duration_seconds=time.monotonic() - start_time,
                            skipped=True,
                        )

                    if error_code == ErrorCode.CANCELLED:
                        return DownloadResult(
                            success=False,
                            url=url,
                            error_code=ErrorCode.CANCELLED,
                            error_message="Download cancelled by user",
                            attempts=attempts,
                            duration_seconds=time.monotonic() - start_time,
                        )

                    should_retry = attempts <= max_retries and _is_retryable(error_code)
                    if not should_retry:
                        return DownloadResult(
                            success=False,
                            url=url,
                            error_code=error_code,
                            error_message=error_message,
                            attempts=attempts,
                            duration_seconds=time.monotonic() - start_time,
                        )

                    delay = min(
                        float(retry_delay) * (retry_backoff ** (attempts - 1)), 10.0
                    )
                    if cancel_event:
                        cancel_event.wait(delay)
                    else:
                        time.sleep(delay)
        except Exception as e:
            return DownloadResult(
                success=False,
                url=url,
                error_code=ErrorCode.PLUGIN_ERROR,
                error_message=_strip_ansi(str(e)),
            )

    # Fallback to yt-dlp
    return DownloadResult(
        success=False,
        url=url,
        error_code=ErrorCode.PLUGIN_ERROR,
        error_message="No suitable plugin found for URL",
    )


def main(argv: list[str] | None = None) -> int:
    """Run the CLI, honoring configuration defaults and explicit overrides."""
    parser = argparse.ArgumentParser(
        description="TubeTracks: Multi-platform media downloader"
    )
    parser.add_argument("url", nargs="?", help="URL to download")
    parser.add_argument(
        "-b", "--batch-file", type=Path, help="Read URLs from a UTF-8 text file"
    )
    parser.add_argument(
        "-p", "--playlist", action="store_true", help="Download the full playlist"
    )
    parser.add_argument("--config", type=Path, help="Configuration file")
    parser.add_argument("-q", "--quality", choices=list(QUALITY_PRESETS))
    parser.add_argument("-f", "--format", choices=SUPPORTED_FORMATS)
    parser.add_argument("-o", "--output", help="Output directory")
    parser.add_argument("-t", "--template", help="yt-dlp filename template")
    parser.add_argument("--proxy", help="HTTP or SOCKS proxy URL")
    parser.add_argument(
        "--limit-rate", dest="rate_limit", help="Rate limit, e.g. 500K or 1M"
    )
    parser.add_argument("--cookies-file", help="Netscape-format cookies file")
    parser.add_argument("--retries", type=int, help="Number of retries after a failure")
    parser.add_argument("--concurrent-downloads", type=int, choices=range(1, 6))
    parser.add_argument("--archive-file", help="Download archive path")
    for name in ("embed-metadata", "embed-thumbnail", "use-archive"):
        parser.add_argument(
            f"--{name}", action=argparse.BooleanOptionalAction, default=None
        )
    parser.add_argument("--quiet", action="store_true", help="Suppress download output")
    parser.add_argument(
        "--dry-run", action="store_true", help="Preview without downloading"
    )
    parser.add_argument(
        "--save-config", action="store_true", help="Save current settings"
    )
    parser.add_argument(
        "--show-config", action="store_true", help="Display current configuration"
    )
    parser.add_argument(
        "--list-plugins", action="store_true", help="List available plugins"
    )
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    args = parser.parse_args(argv)
    config = load_config(str(args.config) if args.config else None)
    for field in (
        "quality",
        "format",
        "output",
        "template",
        "proxy",
        "rate_limit",
        "cookies_file",
        "retries",
        "concurrent_downloads",
        "archive_file",
        "embed_metadata",
        "embed_thumbnail",
        "use_archive",
    ):
        value = getattr(args, field)
        if value is not None:
            setattr(config, field, value)
    config.quiet = args.quiet
    config.dry_run = args.dry_run
    if config.retries < 0 or not 1 <= config.concurrent_downloads <= 5:
        parser.error(
            "retries must be nonnegative and concurrent downloads must be between 1 and 5"
        )

    if args.save_config:
        try:
            config.save_to_file(args.config or DEFAULT_CONFIG_FILE)
        except OSError as exc:
            console.print(f"Error saving configuration: {exc}")
            return 2
        return 0
    if args.show_config:
        console.print("[bold]Configuration:[/bold]")
        console.print(f"  Quality: {config.quality}")
        console.print(f"  Format: {config.format}")
        console.print(f"  Output: {config.output}")
        console.print(f"  Retries: {config.retries}")
        return 0
    if args.list_plugins:
        platforms = list_supported_platforms()
        console.print(f"[bold]Total Plugins: {len(platforms)}[/bold]")
        for caps in platforms.values():
            console.print(f"  {caps['platform']}: {caps['description']}")
        return 0

    urls = [args.url] if args.url else []
    if args.batch_file:
        try:
            urls.extend(
                line.strip()
                for line in args.batch_file.read_text(encoding="utf-8-sig").splitlines()
                if line.strip() and not line.lstrip().startswith("#")
            )
        except (OSError, UnicodeError) as exc:
            console.print(f"Error reading batch file: {exc}")
            return 2
    if not urls:
        parser.print_help()
        return 2
    for url in urls:
        valid, message = validate_url(url)
        if not valid:
            console.print(f"Error: {message}", markup=False)
            return 2

    options = dict(
        output_dir=config.output,
        quality=config.quality,
        audio_format=config.format,
        filename_template=config.template,
        is_playlist=args.playlist,
        proxy=config.proxy,
        rate_limit=config.rate_limit,
        cookies_file=config.cookies_file,
    )
    if args.dry_run:
        success = True
        for url in urls:
            info = dry_run_info(url, **options)
            if info is None:
                success = False
            else:
                console.print(
                    json.dumps(info["videos"], ensure_ascii=False, indent=2),
                    markup=False,
                )
        return 0 if success else 1

    options.update(
        quiet=config.quiet,
        max_retries=config.retries,
        embed_metadata=config.embed_metadata,
        embed_thumbnail=config.embed_thumbnail,
        archive_file=(config.archive_file or str(DEFAULT_ARCHIVE_FILE))
        if config.use_archive
        else None,
    )

    def download(url):
        return download_audio(url, **options)

    with ThreadPoolExecutor(max_workers=config.concurrent_downloads) as executor:
        results = list(executor.map(download, urls))
    if not config.quiet:
        for result in results:
            console.print(str(result), markup=False)
    return 0 if all(result.success for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
