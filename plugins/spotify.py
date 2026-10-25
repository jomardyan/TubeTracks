"""
Spotify converter plugin - extract audio from Spotify tracks/playlists.
Note: Spotify tracks require premium account for direct download via API.
This plugin provides metadata extraction and playlist compilation support.
"""

import re

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities
from .yt_dlp_converter import YtDlpConverter


class SpotifyConverter(YtDlpConverter, BaseConverter):
    """Spotify track and playlist information extractor"""

    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Spotify Converter",
            version="1.5.2",
            platform="Spotify",
            description="Extract metadata from Spotify tracks and create playlists for download",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r"^https?://open\.spotify\.com/track/[\w]+",
                r"^https?://open\.spotify\.com/playlist/[\w]+",
                r"^https?://open\.spotify\.com/album/[\w]+",
                r"^spotify:track:[\w]+",
                r"^spotify:playlist:[\w]+",
            ],
            supported_content_types=[ContentType.AUDIO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=["low", "medium", "high", "best"],
            output_formats=["mp3", "m4a", "ogg", "wav", "flac"],
        )

    def can_handle(self, url: str) -> bool:
        """Check if URL is a Spotify URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False

    def validate_url(self, url: str) -> tuple[bool, str]:
        """Validate Spotify URL format"""
        if not url:
            return False, "URL cannot be empty"

        if self.can_handle(url):
            return True, ""

        return False, f"Invalid Spotify URL format: {url}"
