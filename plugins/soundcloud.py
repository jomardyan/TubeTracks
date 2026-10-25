"""
SoundCloud converter plugin - download audio from SoundCloud tracks.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class SoundCloudConverter(YtDlpConverter, BaseConverter):
    """SoundCloud audio downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="SoundCloud Converter",
            version="1.5.2",
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

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate SoundCloud URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid SoundCloud URL format: {url}"
