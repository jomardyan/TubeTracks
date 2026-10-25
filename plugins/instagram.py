"""
Instagram converter plugin - download videos and audio from Instagram.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class InstagramConverter(YtDlpConverter, BaseConverter):
    """Instagram video and audio downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Instagram Converter",
            version="1.6.0",
            platform="Instagram",
            description="Download videos and audio from Instagram posts and reels",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?instagram\.com/p/[\w-]+",
                r"^https?://(www\.)?instagram\.com/reel/[\w-]+",
                r"^https?://(www\.)?instagram\.com/tv/[\w-]+",
                r"^https?://instagr\.am/p/[\w-]+",
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=False,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high"],
            output_formats=["mp3", "mp4", "m4a"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is an Instagram URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Instagram URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Instagram URL format: {url}"
