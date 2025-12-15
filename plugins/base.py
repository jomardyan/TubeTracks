"""
Base plugin system for multi-platform audio/video converters.

This module provides the abstract base classes and plugin registry for extending
the downloader with support for multiple platforms beyond YouTube.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class ContentType(Enum):
    """Types of content that plugins can handle"""

    AUDIO = "audio"
    VIDEO = "video"
    MIXED = "mixed"


class ExtractorType(Enum):
    """Extractor engine used by the plugin"""

    YT_DLP = "yt-dlp"
    CUSTOM = "custom"
    HYBRID = "hybrid"


@dataclass
class PluginCapabilities:
    """Describes what a plugin is capable of"""

    name: str
    version: str
    platform: str  # e.g., "YouTube", "TikTok", "Spotify"
    description: str
    author: str
    url_patterns: List[str]  # Regex patterns for URL matching
    supported_content_types: List[ContentType]
    supports_playlist: bool = False
    supports_auth: bool = False
    supports_subtitles: bool = False
    supports_metadata: bool = True
    extractor_type: ExtractorType = ExtractorType.YT_DLP
    quality_presets: List[str] = None
    output_formats: List[str] = None

    def __post_init__(self):
        if self.quality_presets is None:
            self.quality_presets = ["low", "medium", "high", "best"]
        if self.output_formats is None:
            self.output_formats = ["mp3", "mp4", "m4a", "wav", "ogg"]


class BaseConverter(ABC):
    """
    Abstract base class for all platform-specific converters.

    Plugins must inherit from this class and implement the required methods.
    """

    def __init__(self):
        self._capabilities: Optional[PluginCapabilities] = None

    @property
    def capabilities(self) -> PluginCapabilities:
        """Get plugin capabilities"""
        if self._capabilities is None:
            self._capabilities = self.get_capabilities()
        return self._capabilities

    @abstractmethod
    def get_capabilities(self) -> PluginCapabilities:
        """
        Return plugin capabilities.

        Returns:
            PluginCapabilities: Information about what this plugin supports
        """
        pass

    @abstractmethod
    def can_handle(self, url: str) -> bool:
        """
        Check if this plugin can handle the given URL.

        Args:
            url: The URL to check

        Returns:
            bool: True if this plugin can handle the URL
        """
        pass

    @abstractmethod
    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """
        Extract metadata and information from the URL without downloading.

        Args:
            url: The URL to extract info from
            **kwargs: Additional plugin-specific options

        Returns:
            dict: Metadata including title, duration, thumbnail, etc.
        """
        pass

    @abstractmethod
    def download(
        self,
        url: str,
        output_path: str,
        quality: str = "medium",
        format: str = "mp3",
        **kwargs,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download and convert content from the URL.

        Args:
            url: The content URL
            output_path: Where to save the file
            quality: Quality preset
            format: Output format
            **kwargs: Additional plugin-specific options (auth, cookies, etc.)

        Returns:
            tuple: (success, file_path, error_message)
                - success: True if download succeeded
                - file_path: Path to downloaded file (if success)
                - error_message: Error message (if failed)
        """
        pass

    @abstractmethod
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """
        Validate if the URL format is correct for this platform.

        Args:
            url: The URL to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        pass

    def supports_playlist(self) -> bool:
        """Check if plugin supports playlist downloads"""
        return self.capabilities.supports_playlist

    def supports_authentication(self) -> bool:
        """Check if plugin requires/supports authentication"""
        return self.capabilities.supports_auth

    def get_quality_presets(self) -> List[str]:
        """Get available quality presets for this platform"""
        return self.capabilities.quality_presets

    def get_output_formats(self) -> List[str]:
        """Get available output formats for this platform"""
        return self.capabilities.output_formats


class PluginRegistry:
    """
    Registry for managing converter plugins.

    Handles plugin registration, discovery, and selection based on URL.
    """

    def __init__(self):
        self._plugins: Dict[str, BaseConverter] = {}
        self._url_pattern_cache: Dict[str, BaseConverter] = {}

    def register(self, plugin_id: str, plugin: BaseConverter) -> None:
        """
        Register a new plugin.

        Args:
            plugin_id: Unique identifier for the plugin
            plugin: An instance of BaseConverter
        """
        if not isinstance(plugin, BaseConverter):
            raise TypeError(f"Plugin must inherit from BaseConverter")

        self._plugins[plugin_id] = plugin
        self._url_pattern_cache.clear()  # Invalidate cache

    def unregister(self, plugin_id: str) -> None:
        """Unregister a plugin"""
        if plugin_id in self._plugins:
            del self._plugins[plugin_id]
            self._url_pattern_cache.clear()

    def get_plugin(self, plugin_id: str) -> Optional[BaseConverter]:
        """Get a specific plugin by ID"""
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> Dict[str, PluginCapabilities]:
        """List all registered plugins with their capabilities"""
        return {pid: plugin.capabilities for pid, plugin in self._plugins.items()}

    def find_plugin_for_url(self, url: str) -> Optional[Tuple[str, BaseConverter]]:
        """
        Find the appropriate plugin for a given URL.

        Args:
            url: The URL to find a plugin for

        Returns:
            tuple: (plugin_id, plugin) or None if no plugin found
        """
        # Check cache first
        if url in self._url_pattern_cache:
            plugin = self._url_pattern_cache[url]
            return (
                next((pid for pid, p in self._plugins.items() if p is plugin), None),
                plugin,
            )

        # Search through registered plugins
        for plugin_id, plugin in self._plugins.items():
            if plugin.can_handle(url):
                # Cache this result (for same URL)
                self._url_pattern_cache[url] = plugin
                return plugin_id, plugin

        return None

    def get_plugins_for_platform(self, platform: str) -> Dict[str, BaseConverter]:
        """Get all plugins for a specific platform (e.g., 'YouTube')"""
        return {
            pid: plugin
            for pid, plugin in self._plugins.items()
            if plugin.capabilities.platform.lower() == platform.lower()
        }

    def get_plugins_by_content_type(
        self, content_type: ContentType
    ) -> Dict[str, BaseConverter]:
        """Get all plugins that support a specific content type"""
        return {
            pid: plugin
            for pid, plugin in self._plugins.items()
            if content_type in plugin.capabilities.supported_content_types
        }

    def get_all_supported_patterns(self) -> List[str]:
        """Get all URL patterns supported by registered plugins"""
        patterns = []
        for plugin in self._plugins.values():
            patterns.extend(plugin.capabilities.url_patterns)
        return patterns

    def __len__(self) -> int:
        """Get number of registered plugins"""
        return len(self._plugins)

    def __contains__(self, plugin_id: str) -> bool:
        """Check if a plugin is registered"""
        return plugin_id in self._plugins

    def __iter__(self):
        """Iterate over all plugins"""
        return iter(self._plugins.items())


# Global plugin registry
_global_registry: Optional[PluginRegistry] = None


def get_global_registry() -> PluginRegistry:
    """Get or create the global plugin registry"""
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry()
    return _global_registry


def reset_global_registry() -> None:
    """Reset the global registry (for testing)"""
    global _global_registry
    _global_registry = None
