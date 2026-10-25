"""
Reddit converter plugin - download videos and audio from Reddit.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class RedditConverter(YtDlpConverter, BaseConverter):
    """Reddit video and audio downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Reddit Converter",
            version="1.5.2",
            platform="Reddit",
            description="Download videos and audio from Reddit posts",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?reddit\.com/r/[\w]+/comments/[\w]+",
                r"^https?://reddit\.com/r/[\w]+/comments/[\w]+",
                r"^https?://(www\.)?reddit\.com/user/[\w]+",
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
        """Check if URL is a Reddit URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Reddit URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Reddit URL format: {url}"
