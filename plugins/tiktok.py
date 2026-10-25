"""
TikTok converter plugin - download videos and audio from TikTok.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class TikTokConverter(YtDlpConverter, BaseConverter):
    """TikTok video and audio downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="TikTok Converter",
            version="1.5.2",
            platform="TikTok",
            description="Download videos and extract audio from TikTok",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?tiktok\.com/@[\w\.]+/video/\d+",
                r"^https?://(www\.)?tiktok\.com/\@[\w\.]+/video/\d+",
                r"^https?://vm\.tiktok\.com/[\w]+",
                r"^https?://vt\.tiktok\.com/[\w]+",
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high"],
            output_formats=["mp3", "mp4", "m4a"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a TikTok URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate TikTok URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid TikTok URL format: {url}"
