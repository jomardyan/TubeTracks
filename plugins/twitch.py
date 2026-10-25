"""
Twitch converter plugin - download videos and clips from Twitch.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class TwitchConverter(YtDlpConverter, BaseConverter):
    """Twitch video and clip downloader"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Twitch Converter",
            version="1.6.0",
            platform="Twitch",
            description="Download VODs, clips, and highlights from Twitch",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://(www\.)?twitch\.tv/[\w]+/clip/[\w]+",
                r"^https?://(www\.)?twitch\.tv/videos/\d+",
                r"^https?://clips\.twitch\.tv/[\w]+",
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=False,
            supports_auth=False,
            supports_subtitles=True,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high", "best"],
            output_formats=["mp3", "mp4", "m4a"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Twitch URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Twitch URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Twitch URL format: {url}"
