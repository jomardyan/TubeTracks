"""
Plugin system for multi-platform audio/video converters.

Provides a registry-based plugin architecture for extending the downloader
with support for multiple platforms beyond YouTube.
"""

from .base import (BaseConverter, ContentType, ExtractorType,
                   PluginCapabilities, PluginRegistry, get_global_registry,
                   reset_global_registry)
from .dailymotion import DailymotionConverter
from .instagram import InstagramConverter
from .reddit import RedditConverter
from .soundcloud import SoundCloudConverter
from .spotify import SpotifyConverter
from .tiktok import TikTokConverter
from .twitch import TwitchConverter
from .vimeo import VimeoConverter
from .youtube import YouTubeConverter


def register_default_plugins():
    """Register all default platform plugins"""
    registry = get_global_registry()
    
    # Register top 10 most popular platforms
    plugins = [
        ('youtube', YouTubeConverter()),
        ('tiktok', TikTokConverter()),
        ('instagram', InstagramConverter()),
        ('soundcloud', SoundCloudConverter()),
        ('spotify', SpotifyConverter()),
        ('twitch', TwitchConverter()),
        ('dailymotion', DailymotionConverter()),
        ('vimeo', VimeoConverter()),
        ('reddit', RedditConverter()),
    ]
    
    for plugin_id, converter in plugins:
        registry.register(plugin_id, converter)
    
    return registry


# Auto-register default plugins when module is imported
_registry = register_default_plugins()


__all__ = [
    # Core classes
    'BaseConverter',
    'PluginCapabilities',
    'PluginRegistry',
    'ContentType',
    'ExtractorType',
    
    # Functions
    'get_global_registry',
    'reset_global_registry',
    'register_default_plugins',
    
    # Converters
    'YouTubeConverter',
    'TikTokConverter',
    'InstagramConverter',
    'SoundCloudConverter',
    'SpotifyConverter',
    'TwitchConverter',
    'DailymotionConverter',
    'VimeoConverter',
    'RedditConverter',
]
