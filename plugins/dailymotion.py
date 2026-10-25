"""
Dailymotion converter plugin - download videos from Dailymotion.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class DailymotionConverter(YtDlpConverter, BaseConverter):
    """Dailymotion video downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Dailymotion Converter",
            version="1.6.0",
            platform="Dailymotion",
            description="Download videos from Dailymotion",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?dailymotion\.com/video/[\w]+",
                r"^https?://dai\.ly/[\w]+",
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=True,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high"],
            output_formats=["mp3", "mp4", "m4a"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Dailymotion URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Dailymotion URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Dailymotion URL format: {url}"
