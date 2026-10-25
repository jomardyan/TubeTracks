"""
YouTube converter plugin - wrapper around yt-dlp's native YouTube support.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class YouTubeConverter(YtDlpConverter, BaseConverter):
    """YouTube audio and video downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="YouTube Converter",
            version="1.6.0",
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

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate YouTube URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid YouTube URL format: {url}"
