"""
SoundCloud converter plugin - download audio from SoundCloud tracks.
"""

import re
from typing import Any, Dict, Optional, Tuple

import yt_dlp

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities


class SoundCloudConverter(BaseConverter):
    """SoundCloud audio downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="SoundCloud Converter",
            version="1.0.0",
            platform="SoundCloud",
            description="Download audio tracks from SoundCloud",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://soundcloud\.com/[\w-]+/[\w-]+",
                r"^https?://soundcloud\.com/[\w-]+",
                r"^https?://soundcloud\.app\.goo\.gl/[\w]+",
            ],
            supported_content_types=[ContentType.AUDIO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high"],
            output_formats=["mp3", "m4a", "ogg", "wav"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a SoundCloud URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate SoundCloud URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid SoundCloud URL format: {url}"

    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from SoundCloud URL"""
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
                    "comment_count": info.get("comment_count", 0),
                    "is_playlist": "entries" in info,
                    "video_count": (
                        len(info.get("entries", [])) if "entries" in info else 1
                    ),
                }
        except Exception as e:
            raise RuntimeError(f"Failed to extract SoundCloud info: {e}")

    def download(
        self,
        url: str,
        output_path: str,
        quality: str = "medium",
        format: str = "mp3",
        **kwargs,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download audio from SoundCloud"""
        try:
            from pathlib import Path

            Path(output_path).mkdir(parents=True, exist_ok=True)

            bitrates = {
                "low": "128",
                "medium": "192",
                "high": "320",
            }
            bitrate = bitrates.get(quality, "192")

            postprocessors = []
            if format == "mp3":
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": bitrate,
                    }
                )

            ydl_opts = {
                "format": "best",
                "postprocessors": postprocessors,
                "outtmpl": f"{output_path}/%(title)s.%(ext)s",
                "quiet": kwargs.get("quiet", False),
                "no_warnings": kwargs.get("quiet", False),
                "noplaylist": not kwargs.get("is_playlist", False),
            }

            if kwargs.get("proxy"):
                ydl_opts["proxy"] = kwargs["proxy"]
            if kwargs.get("rate_limit"):
                ydl_opts["ratelimit"] = kwargs["rate_limit"]

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
            return False, None, f"SoundCloud download failed: {str(e)}"
