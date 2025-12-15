"""
YouTube converter plugin - wrapper around yt-dlp's native YouTube support.
"""

import re
from typing import Any, Dict, List, Optional, Tuple

import yt_dlp

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities


class YouTubeConverter(BaseConverter):
    """YouTube audio and video downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="YouTube Converter",
            version="1.0.0",
            platform="YouTube",
            description="Download audio and video from YouTube videos, playlists, and shorts",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?youtube\.com/watch\?v=[\w-]+",
                r"^https?://(www\.)?youtube\.com/playlist\?list=[\w-]+",
                r"^https?://youtu\.be/[\w-]+",
                r"^https?://(www\.)?youtube\.com/shorts/[\w-]+",
                r"^https?://music\.youtube\.com/watch\?v=[\w-]+",
            ],
            supported_content_types=[
                ContentType.AUDIO,
                ContentType.VIDEO,
                ContentType.MIXED,
            ],
            supports_playlist=True,
            supports_auth=True,
            supports_subtitles=True,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high", "best"],
            output_formats=["mp3", "mp4", "m4a", "wav", "ogg", "flac"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a YouTube URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate YouTube URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid YouTube URL format: {url}"

    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from YouTube URL"""
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": not kwargs.get("is_playlist", False),
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)

                return {
                    "title": info.get("title", "Unknown"),
                    "duration": info.get("duration", 0),
                    "thumbnail": info.get("thumbnail", None),
                    "uploader": info.get("uploader", "Unknown"),
                    "description": info.get("description", ""),
                    "view_count": info.get("view_count", 0),
                    "like_count": info.get("like_count", 0),
                    "upload_date": info.get("upload_date", ""),
                    "is_playlist": "entries" in info,
                    "video_count": (
                        len(info.get("entries", [])) if "entries" in info else 1
                    ),
                }
        except Exception as e:
            raise RuntimeError(f"Failed to extract YouTube info: {e}")

    def download(
        self,
        url: str,
        output_path: str,
        quality: str = "medium",
        format: str = "mp3",
        **kwargs,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download and convert YouTube content"""
        try:
            import time
            from pathlib import Path

            Path(output_path).mkdir(parents=True, exist_ok=True)

            # Quality bitrates
            bitrates = {
                "low": "128",
                "medium": "192",
                "high": "320",
                "best": "0",
            }
            bitrate = bitrates.get(quality, "192")

            postprocessors = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": format,
                    "preferredquality": bitrate,
                }
            ]

            if kwargs.get("embed_metadata", True):
                postprocessors.append({"key": "FFmpegMetadata"})

            if kwargs.get("embed_thumbnail", True):
                postprocessors.append({"key": "EmbedThumbnail"})

            ydl_opts = {
                "format": "bestaudio/best",
                "postprocessors": postprocessors,
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "quiet": kwargs.get("quiet", False),
                "no_warnings": kwargs.get("quiet", False),
                "writethumbnail": kwargs.get("embed_thumbnail", True),
                "noplaylist": not kwargs.get("is_playlist", False),
                "continuedl": True,
            }

            # Add optional parameters
            if kwargs.get("proxy"):
                ydl_opts["proxy"] = kwargs["proxy"]
            if kwargs.get("cookies_file"):
                ydl_opts["cookiefile"] = kwargs["cookies_file"]
            if kwargs.get("rate_limit"):
                ydl_opts["ratelimit"] = kwargs["rate_limit"]
            if kwargs.get("archive_file"):
                ydl_opts["download_archive"] = kwargs["archive_file"]

            downloaded_file = None

            class ProgressHook:
                def __call__(self, d):
                    nonlocal downloaded_file
                    if d["status"] == "finished":
                        downloaded_file = d.get("filename")

            ydl_opts["progress_hooks"] = [ProgressHook()]

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            return True, downloaded_file, None

        except Exception as e:
            return False, None, f"YouTube download failed: {str(e)}"
