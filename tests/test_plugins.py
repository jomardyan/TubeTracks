"""
Tests for the plugin system and platform converters
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import plugins module - this will auto-register all plugins
import plugins
from plugins import (BaseConverter, ContentType, DailymotionConverter,
                     ExtractorType, InstagramConverter, PluginCapabilities,
                     PluginRegistry, RedditConverter, SoundCloudConverter,
                     SpotifyConverter, TikTokConverter, TwitchConverter,
                     VimeoConverter, YouTubeConverter, get_global_registry,
                     register_default_plugins, reset_global_registry)

# Ensure plugins are registered
register_default_plugins()


@pytest.fixture(scope="module", autouse=True)
def ensure_plugins_registered():
    """Ensure all plugins are registered before running tests"""
    register_default_plugins()
    yield


class TestPluginRegistry:
    """Tests for the PluginRegistry class"""
    
    def test_registry_singleton(self):
        """Test that get_global_registry returns the same instance"""
        registry1 = get_global_registry()
        registry2 = get_global_registry()
        assert registry1 is registry2
    
    def test_registry_reset(self):
        """Test resetting the global registry"""
        registry1 = get_global_registry()
        reset_global_registry()
        registry2 = get_global_registry()
        assert registry1 is not registry2
        # Re-register for other tests
        register_default_plugins()
    
    def test_register_plugin(self):
        """Test registering a new plugin"""
        registry = PluginRegistry()
        converter = YouTubeConverter()
        registry.register('test_youtube', converter)
        
        assert 'test_youtube' in registry
        assert len(registry) == 1
    
    def test_unregister_plugin(self):
        """Test unregistering a plugin"""
        registry = PluginRegistry()
        converter = YouTubeConverter()
        registry.register('test_youtube', converter)
        
        registry.unregister('test_youtube')
        assert 'test_youtube' not in registry
        assert len(registry) == 0
    
    def test_get_plugin(self):
        """Test getting a specific plugin"""
        registry = PluginRegistry()
        converter = YouTubeConverter()
        registry.register('test_youtube', converter)
        
        retrieved = registry.get_plugin('test_youtube')
        assert retrieved is converter
    
    def test_list_plugins(self):
        """Test listing all plugins"""
        registry = PluginRegistry()
        registry.register('youtube', YouTubeConverter())
        registry.register('tiktok', TikTokConverter())
        
        plugins = registry.list_plugins()
        assert len(plugins) == 2
        assert 'youtube' in plugins
        assert 'tiktok' in plugins
    
    def test_find_plugin_for_url_youtube(self):
        """Test finding YouTube plugin from URL"""
        registry = PluginRegistry()
        registry.register('youtube', YouTubeConverter())
        
        result = registry.find_plugin_for_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        assert result is not None
        plugin_id, converter = result
        assert plugin_id == 'youtube'
        assert isinstance(converter, YouTubeConverter)
    
    def test_find_plugin_for_url_not_found(self):
        """Test finding plugin for unsupported URL"""
        registry = PluginRegistry()
        registry.register('youtube', YouTubeConverter())
        
        result = registry.find_plugin_for_url('https://unsupported-site.com/video')
        assert result is None
    
    def test_get_plugins_by_content_type(self):
        """Test filtering plugins by content type"""
        registry = PluginRegistry()
        registry.register('youtube', YouTubeConverter())
        registry.register('soundcloud', SoundCloudConverter())
        
        audio_plugins = registry.get_plugins_by_content_type(ContentType.AUDIO)
        assert len(audio_plugins) >= 2


class TestYouTubeConverter:
    """Tests for YouTube converter plugin"""
    
    def test_capabilities(self):
        """Test YouTube converter capabilities"""
        converter = YouTubeConverter()
        caps = converter.capabilities
        
        assert caps.platform == "YouTube"
        assert caps.supports_playlist is True
        assert caps.supports_auth is True
        assert ContentType.AUDIO in caps.supported_content_types
        assert 'mp3' in caps.output_formats
    
    def test_can_handle_youtube_watch(self):
        """Test YouTube watch URL recognition"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://www.youtube.com/watch?v=dQw4w9WgXcQ') is True
    
    def test_can_handle_youtube_short_url(self):
        """Test YouTube short URL recognition"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://youtu.be/dQw4w9WgXcQ') is True
    
    def test_can_handle_youtube_shorts(self):
        """Test YouTube Shorts URL recognition"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://www.youtube.com/shorts/abc123') is True
    
    def test_can_handle_youtube_music(self):
        """Test YouTube Music URL recognition"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://music.youtube.com/watch?v=dQw4w9WgXcQ') is True
    
    def test_can_handle_youtube_playlist(self):
        """Test YouTube playlist URL recognition"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://www.youtube.com/playlist?list=PLtest') is True
    
    def test_cannot_handle_non_youtube(self):
        """Test rejection of non-YouTube URLs"""
        converter = YouTubeConverter()
        assert converter.can_handle('https://vimeo.com/123456') is False
    
    def test_validate_url_success(self):
        """Test YouTube URL validation success"""
        converter = YouTubeConverter()
        valid, msg = converter.validate_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        assert valid is True
        assert msg == ""
    
    def test_validate_url_failure(self):
        """Test YouTube URL validation failure"""
        converter = YouTubeConverter()
        valid, msg = converter.validate_url('https://invalid.com/video')
        assert valid is False
        assert len(msg) > 0


class TestTikTokConverter:
    """Tests for TikTok converter plugin"""
    
    def test_capabilities(self):
        """Test TikTok converter capabilities"""
        converter = TikTokConverter()
        caps = converter.capabilities
        
        assert caps.platform == "TikTok"
        assert caps.supports_playlist is True
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_tiktok_video(self):
        """Test TikTok video URL recognition"""
        converter = TikTokConverter()
        assert converter.can_handle('https://www.tiktok.com/@user/video/123456789') is True
    
    def test_can_handle_tiktok_short_url(self):
        """Test TikTok short URL recognition"""
        converter = TikTokConverter()
        assert converter.can_handle('https://vm.tiktok.com/abc123') is True
    
    def test_cannot_handle_non_tiktok(self):
        """Test rejection of non-TikTok URLs"""
        converter = TikTokConverter()
        assert converter.can_handle('https://youtube.com/watch?v=123') is False


class TestInstagramConverter:
    """Tests for Instagram converter plugin"""
    
    def test_capabilities(self):
        """Test Instagram converter capabilities"""
        converter = InstagramConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Instagram"
        assert caps.supports_playlist is False
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_instagram_post(self):
        """Test Instagram post URL recognition"""
        converter = InstagramConverter()
        assert converter.can_handle('https://www.instagram.com/p/ABC123/') is True
    
    def test_can_handle_instagram_reel(self):
        """Test Instagram reel URL recognition"""
        converter = InstagramConverter()
        assert converter.can_handle('https://www.instagram.com/reel/ABC123/') is True
    
    def test_can_handle_instagram_tv(self):
        """Test Instagram TV URL recognition"""
        converter = InstagramConverter()
        assert converter.can_handle('https://www.instagram.com/tv/ABC123/') is True
    
    def test_cannot_handle_non_instagram(self):
        """Test rejection of non-Instagram URLs"""
        converter = InstagramConverter()
        assert converter.can_handle('https://tiktok.com/@user/video/123') is False


class TestSoundCloudConverter:
    """Tests for SoundCloud converter plugin"""
    
    def test_capabilities(self):
        """Test SoundCloud converter capabilities"""
        converter = SoundCloudConverter()
        caps = converter.capabilities
        
        assert caps.platform == "SoundCloud"
        assert caps.supports_playlist is True
        assert ContentType.AUDIO in caps.supported_content_types
        assert 'mp3' in caps.output_formats
    
    def test_can_handle_soundcloud_track(self):
        """Test SoundCloud track URL recognition"""
        converter = SoundCloudConverter()
        assert converter.can_handle('https://soundcloud.com/artist/track-name') is True
    
    def test_can_handle_soundcloud_user(self):
        """Test SoundCloud user URL recognition"""
        converter = SoundCloudConverter()
        assert converter.can_handle('https://soundcloud.com/artist-name') is True
    
    def test_cannot_handle_non_soundcloud(self):
        """Test rejection of non-SoundCloud URLs"""
        converter = SoundCloudConverter()
        assert converter.can_handle('https://youtube.com/watch?v=123') is False


class TestSpotifyConverter:
    """Tests for Spotify converter plugin"""
    
    def test_capabilities(self):
        """Test Spotify converter capabilities"""
        converter = SpotifyConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Spotify"
        assert caps.supports_playlist is True
        assert ContentType.AUDIO in caps.supported_content_types
    
    def test_can_handle_spotify_track(self):
        """Test Spotify track URL recognition"""
        converter = SpotifyConverter()
        assert converter.can_handle('https://open.spotify.com/track/abc123') is True
    
    def test_can_handle_spotify_playlist(self):
        """Test Spotify playlist URL recognition"""
        converter = SpotifyConverter()
        assert converter.can_handle('https://open.spotify.com/playlist/abc123') is True
    
    def test_can_handle_spotify_album(self):
        """Test Spotify album URL recognition"""
        converter = SpotifyConverter()
        assert converter.can_handle('https://open.spotify.com/album/abc123') is True
    
    def test_cannot_handle_non_spotify(self):
        """Test rejection of non-Spotify URLs"""
        converter = SpotifyConverter()
        assert converter.can_handle('https://soundcloud.com/artist/track') is False


class TestTwitchConverter:
    """Tests for Twitch converter plugin"""
    
    def test_capabilities(self):
        """Test Twitch converter capabilities"""
        converter = TwitchConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Twitch"
        assert caps.supports_subtitles is True
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_twitch_video(self):
        """Test Twitch video URL recognition"""
        converter = TwitchConverter()
        assert converter.can_handle('https://www.twitch.tv/videos/123456789') is True
    
    def test_can_handle_twitch_clip(self):
        """Test Twitch clip URL recognition"""
        converter = TwitchConverter()
        assert converter.can_handle('https://www.twitch.tv/user/clip/ClipSlug') is True
        assert converter.can_handle('https://clips.twitch.tv/ClipSlug') is True
    
    def test_cannot_handle_non_twitch(self):
        """Test rejection of non-Twitch URLs"""
        converter = TwitchConverter()
        assert converter.can_handle('https://youtube.com/watch?v=123') is False


class TestDailymotionConverter:
    """Tests for Dailymotion converter plugin"""
    
    def test_capabilities(self):
        """Test Dailymotion converter capabilities"""
        converter = DailymotionConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Dailymotion"
        assert caps.supports_playlist is True
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_dailymotion_video(self):
        """Test Dailymotion video URL recognition"""
        converter = DailymotionConverter()
        assert converter.can_handle('https://www.dailymotion.com/video/x123abc') is True
    
    def test_can_handle_dailymotion_short_url(self):
        """Test Dailymotion short URL recognition"""
        converter = DailymotionConverter()
        assert converter.can_handle('https://dai.ly/x123abc') is True
    
    def test_cannot_handle_non_dailymotion(self):
        """Test rejection of non-Dailymotion URLs"""
        converter = DailymotionConverter()
        assert converter.can_handle('https://vimeo.com/123456') is False


class TestVimeoConverter:
    """Tests for Vimeo converter plugin"""
    
    def test_capabilities(self):
        """Test Vimeo converter capabilities"""
        converter = VimeoConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Vimeo"
        assert caps.supports_playlist is True
        assert caps.supports_subtitles is True
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_vimeo_video(self):
        """Test Vimeo video URL recognition"""
        converter = VimeoConverter()
        assert converter.can_handle('https://vimeo.com/123456789') is True
    
    def test_can_handle_vimeo_groups(self):
        """Test Vimeo groups URL recognition"""
        converter = VimeoConverter()
        assert converter.can_handle('https://vimeo.com/groups/shortfilms/videos/123456789') is True
    
    def test_can_handle_vimeo_channels(self):
        """Test Vimeo channels URL recognition"""
        converter = VimeoConverter()
        assert converter.can_handle('https://vimeo.com/channels/staffpicks/123456789') is True
    
    def test_cannot_handle_non_vimeo(self):
        """Test rejection of non-Vimeo URLs"""
        converter = VimeoConverter()
        assert converter.can_handle('https://youtube.com/watch?v=123') is False


class TestRedditConverter:
    """Tests for Reddit converter plugin"""
    
    def test_capabilities(self):
        """Test Reddit converter capabilities"""
        converter = RedditConverter()
        caps = converter.capabilities
        
        assert caps.platform == "Reddit"
        assert caps.supports_playlist is False
        assert ContentType.VIDEO in caps.supported_content_types
    
    def test_can_handle_reddit_post(self):
        """Test Reddit post URL recognition"""
        converter = RedditConverter()
        assert converter.can_handle('https://www.reddit.com/r/videos/comments/abc123') is True
        assert converter.can_handle('https://reddit.com/r/music/comments/xyz789') is True
    
    def test_cannot_handle_non_reddit(self):
        """Test rejection of non-Reddit URLs"""
        converter = RedditConverter()
        assert converter.can_handle('https://youtube.com/watch?v=123') is False


class TestGlobalRegistry:
    """Tests for the global plugin registry"""
    
    def test_global_registry_has_plugins(self):
        """Test that global registry is pre-populated"""
        registry = get_global_registry()
        assert len(registry) > 0
    
    def test_global_registry_has_youtube(self):
        """Test that YouTube plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('youtube')
        assert plugin is not None
        assert isinstance(plugin, YouTubeConverter)
    
    def test_global_registry_has_tiktok(self):
        """Test that TikTok plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('tiktok')
        assert plugin is not None
        assert isinstance(plugin, TikTokConverter)
    
    def test_global_registry_has_instagram(self):
        """Test that Instagram plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('instagram')
        assert plugin is not None
        assert isinstance(plugin, InstagramConverter)
    
    def test_global_registry_has_soundcloud(self):
        """Test that SoundCloud plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('soundcloud')
        assert plugin is not None
        assert isinstance(plugin, SoundCloudConverter)
    
    def test_global_registry_has_spotify(self):
        """Test that Spotify plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('spotify')
        assert plugin is not None
        assert isinstance(plugin, SpotifyConverter)
    
    def test_global_registry_has_twitch(self):
        """Test that Twitch plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('twitch')
        assert plugin is not None
        assert isinstance(plugin, TwitchConverter)
    
    def test_global_registry_has_dailymotion(self):
        """Test that Dailymotion plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('dailymotion')
        assert plugin is not None
        assert isinstance(plugin, DailymotionConverter)
    
    def test_global_registry_has_vimeo(self):
        """Test that Vimeo plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('vimeo')
        assert plugin is not None
        assert isinstance(plugin, VimeoConverter)
    
    def test_global_registry_has_reddit(self):
        """Test that Reddit plugin is registered"""
        registry = get_global_registry()
        plugin = registry.get_plugin('reddit')
        assert plugin is not None
        assert isinstance(plugin, RedditConverter)
    
    def test_global_registry_url_routing(self):
        """Test URL routing through global registry"""
        registry = get_global_registry()
        
        test_cases = [
            ('https://www.youtube.com/watch?v=dQw4w9WgXcQ', 'youtube'),
            ('https://www.tiktok.com/@user/video/123', 'tiktok'),
            ('https://www.instagram.com/p/ABC123/', 'instagram'),
            ('https://soundcloud.com/artist/track', 'soundcloud'),
            ('https://open.spotify.com/track/123', 'spotify'),
            ('https://www.twitch.tv/videos/123', 'twitch'),
            ('https://www.dailymotion.com/video/x123', 'dailymotion'),
            ('https://vimeo.com/123456789', 'vimeo'),
            ('https://reddit.com/r/videos/comments/abc', 'reddit'),
        ]
        
        for url, expected_plugin_id in test_cases:
            result = registry.find_plugin_for_url(url)
            assert result is not None, f"No plugin found for {url}"
            plugin_id, converter = result
            assert plugin_id == expected_plugin_id, f"Expected {expected_plugin_id} for {url}, got {plugin_id}"


class TestPluginCapabilities:
    """Tests for PluginCapabilities dataclass"""
    
    def test_capabilities_defaults(self):
        """Test default values in PluginCapabilities"""
        caps = PluginCapabilities(
            name="Test Plugin",
            version="1.0.0",
            platform="TestPlatform",
            description="Test description",
            author="Test Author",
            url_patterns=[r'^https://test\.com'],
            supported_content_types=[ContentType.AUDIO],
        )
        
        assert caps.supports_playlist is False
        assert caps.supports_auth is False
        assert caps.supports_subtitles is False
        assert caps.supports_metadata is True
        assert caps.extractor_type == ExtractorType.YT_DLP
        assert caps.quality_presets == ['low', 'medium', 'high', 'best']
        assert 'mp3' in caps.output_formats


class TestPluginIntegration:
    """Integration tests for plugin system with downloader"""
    
    def test_validate_url_with_plugins(self):
        """Test that validate_url works with plugin system"""
        from downloader import validate_url

        # YouTube URL
        valid, msg = validate_url('https://www.youtube.com/watch?v=dQw4w9WgXcQ')
        assert valid is True
        
        # TikTok URL
        valid, msg = validate_url('https://www.tiktok.com/@user/video/123')
        assert valid is True
        
        # Invalid URL
        valid, msg = validate_url('https://totally-unsupported-site.com/video')
        assert valid is False
        assert "Unsupported" in msg or "supported platforms" in msg.lower()
    
    def test_list_supported_platforms(self):
        """Test listing supported platforms"""
        from downloader import list_supported_platforms
        
        platforms = list_supported_platforms()
        assert len(platforms) >= 9
        
        # Check that major platforms are present
        platform_names = [p['platform'] for p in platforms.values()]
        assert 'YouTube' in platform_names
        assert 'TikTok' in platform_names
        assert 'Instagram' in platform_names
        assert 'SoundCloud' in platform_names
    
    def test_get_converter_for_url(self):
        """Test getting converter for URL"""
        from downloader import get_converter_for_url
        
        result = get_converter_for_url('https://www.youtube.com/watch?v=123')
        assert result is not None
        
        plugin_id, converter = result
        assert plugin_id == 'youtube'
        assert isinstance(converter, YouTubeConverter)


class TestCLIPluginIntegration:
    """Tests for CLI integration with plugins"""
    
    def test_list_plugins_flag(self):
        """Test --list-plugins CLI flag"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py", "--list-plugins"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0
        assert "YouTube" in result.stdout
        assert "TikTok" in result.stdout
        assert "Total Plugins:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
