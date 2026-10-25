"""
Vimeo converter plugin - download videos from Vimeo.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class VimeoConverter(YtDlpConverter, BaseConverter):
    """Vimeo video downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Vimeo Converter",
            version="1.5.2",
            platform="Vimeo",
            description="Download videos from Vimeo",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?vimeo\.com/\d+",
                r"^https?://(www\.)?vimeo\.com/groups/[\w-]+/videos/\d+",
                r"^https?://(www\.)?vimeo\.com/channels/[\w-]+/\d+",
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=True,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high", "best"],
            output_formats=["mp3", "mp4", "m4a"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Vimeo URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Vimeo URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Vimeo URL format: {url}"
