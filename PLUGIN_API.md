# Plugin System API Documentation

## Overview

  The audiodownload-yt plugin system provides a clean, extensible architecture for adding support for new content platforms. The system is built around the concept of **converters** - pluggable modules that handle downloading and converting content from specific platforms.

## Architecture

### Core Components

#### 1. `BaseConverter` (Abstract Base Class)

All platform-specific converters must inherit from `BaseConverter`. This class defines the interface that all plugins must implement.

```python
from plugins.base import BaseConverter, PluginCapabilities, ContentType

class MyConverter(BaseConverter):
    def get_capabilities(self) -> PluginCapabilities:
        """Define what this plugin supports"""
        pass
    
    def can_handle(self, url: str) -> bool:
        """Check if this plugin can handle a URL"""
        pass
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate URL format"""
        pass
    
    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata without downloading"""
        pass
    
    def download(self, url: str, output_path: str, quality: str = 'medium', 
                 format: str = 'mp3', **kwargs) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download and convert content"""
        pass
```

#### 2. `PluginCapabilities` (Dataclass)

Describes what a plugin is capable of:

```python
@dataclass
class PluginCapabilities:
    name: str                              # Plugin name
    version: str                           # Plugin version
    platform: str                          # Platform name (e.g., "YouTube")
    description: str                       # Brief description
    author: str                            # Author/maintainer
    url_patterns: List[str]               # Regex patterns for URL matching
    supported_content_types: List[ContentType]  # What content it supports
    supports_playlist: bool = False       # Playlist support
    supports_auth: bool = False           # Authentication needed
    supports_subtitles: bool = False      # Subtitle extraction
    supports_metadata: bool = True        # Metadata embedding
    extractor_type: ExtractorType = ExtractorType.YT_DLP
    quality_presets: List[str] = None     # Available quality levels
    output_formats: List[str] = None      # Supported output formats
```

#### 3. `PluginRegistry` (Global Registry)

Manages all registered plugins and handles plugin discovery:

```python
from plugins import get_global_registry

registry = get_global_registry()

# List all plugins
all_plugins = registry.list_plugins()

# Find plugin for URL
plugin_id, converter = registry.find_plugin_for_url(url)

# Register new plugin
registry.register('myplugin', MyConverter())

# Get specific plugin
plugin = registry.get_plugin('youtube')
```

### Shared yt-dlp adapter

Built-in converters inherit `YtDlpConverter` from `plugins.yt_dlp_converter` before
`BaseConverter`. It supplies `get_info()` and `download()` with consistent format
conversion, proxy/cookie/rate options, archive handling, cancellation, and final
output paths. New yt-dlp plugins can reuse this adapter and implement only their
capabilities, URL matching, and URL validation. Custom extractors can continue
implementing the `BaseConverter` methods directly.

## Creating a New Plugin

### Step 1: Create Plugin File

Create a new file in the `plugins/` directory (e.g., `plugins/newplatform.py`):

```python
import re
from typing import Dict, Tuple, Any, Optional
import yt_dlp

from .base import BaseConverter, PluginCapabilities, ContentType, ExtractorType


class NewPlatformConverter(BaseConverter):
    """Download from NewPlatform"""
    
    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="NewPlatform Converter",
            version="1.5.2",
            platform="NewPlatform",
            description="Download content from NewPlatform",
            author="Your Name",
            url_patterns=[
                r'^https?://(www\.)?newplatform\.com/[\w/]+',
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=True,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=['low', 'medium', 'high', 'best'],
            output_formats=['mp3', 'mp4', 'm4a', 'wav', 'ogg', 'flac'],
        )
    
    def can_handle(self, url: str) -> bool:
        """Check if URL belongs to NewPlatform"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate URL format"""
        if not url:
            return False, "URL cannot be empty"
        
        if self.can_handle(url):
            return True, ""
        
        return False, f"Invalid NewPlatform URL format: {url}"
    
    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from URL"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'noplaylist': not kwargs.get('is_playlist', False),
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'uploader': info.get('uploader', 'Unknown'),
                    'description': info.get('description', ''),
                    'is_playlist': 'entries' in info,
                    'video_count': len(info.get('entries', [])) if 'entries' in info else 1,
                }
        except Exception as e:
            raise RuntimeError(f"Failed to extract info: {e}")
    
    def download(
        self,
        url: str,
        output_path: str,
        quality: str = 'medium',
        format: str = 'mp3',
        **kwargs
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download and convert content"""
        try:
            from pathlib import Path
            
            Path(output_path).mkdir(parents=True, exist_ok=True)
            
            bitrates = {
                'low': '128',
                'medium': '192',
                'high': '320',
                'best': '0',
            }
            bitrate = bitrates.get(quality, '192')
            
            postprocessors = []
            if format == 'mp3':
                postprocessors.append({
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': bitrate,
                })
            
            ydl_opts = {
                'format': 'best',
                'postprocessors': postprocessors,
                'outtmpl': f'{output_path}/%(title)s.%(ext)s',
                'quiet': kwargs.get('quiet', False),
                'no_warnings': kwargs.get('quiet', False),
            }
            
            # Add optional network parameters
            if kwargs.get('proxy'):
                ydl_opts['proxy'] = kwargs['proxy']
            if kwargs.get('rate_limit'):
                ydl_opts['ratelimit'] = kwargs['rate_limit']
            
            downloaded_file = None
            
            class ProgressHook:
                def __call__(self, d):
                    nonlocal downloaded_file
                    if d['status'] == 'finished':
                        downloaded_file = d.get('filename')
            
            ydl_opts['progress_hooks'] = [ProgressHook()]
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            return True, downloaded_file, None
        
        except Exception as e:
            return False, None, f"Download failed: {str(e)}"
```

### Step 2: Register Plugin

Update `plugins/__init__.py` to register your new plugin:

```python
from .newplatform import NewPlatformConverter

def register_default_plugins():
    registry = get_global_registry()
    
    # ... existing registrations ...
    
    registry.register('newplatform', NewPlatformConverter())
    
    return registry
```

Add it to `__all__`:

```python
__all__ = [
    # ... existing exports ...
    'NewPlatformConverter',
]
```

### Step 3: Test Your Plugin

Test that your plugin registers and handles URLs correctly:

```bash
python downloader.py --list-plugins
```

Should show your new platform in the list.

Test with a URL:

```bash
python downloader.py https://newplatform.com/your-content
```

## API Reference

### BaseConverter Methods

#### `get_capabilities() -> PluginCapabilities`

**Required.** Return capabilities information.

**Returns:** PluginCapabilities instance

---

#### `can_handle(url: str) -> bool`

**Required.** Check if this converter can handle the given URL.

**Args:**
- `url`: Content URL to check

**Returns:** `True` if converter handles this URL, `False` otherwise

---

#### `validate_url(url: str) -> Tuple[bool, str]`

**Required.** Validate URL format.

**Args:**
- `url`: URL to validate

**Returns:** Tuple of (is_valid, error_message)

---

#### `get_info(url: str, **kwargs) -> Dict[str, Any]`

**Required.** Extract metadata without downloading.

**Args:**
- `url`: Content URL
- `**kwargs`: Plugin-specific options (is_playlist, etc.)

**Returns:** Dictionary with metadata

**Expected keys:**
- `title` (str)
- `duration` (int): seconds
- `thumbnail` (str, optional)
- `uploader` (str, optional)
- `description` (str, optional)
- `is_playlist` (bool)
- `video_count` (int)

---

#### `download(url: str, output_path: str, quality: str = 'medium', format: str = 'mp3', **kwargs) -> Tuple[bool, Optional[str], Optional[str]]`

**Required.** Download and convert content.

**Args:**
- `url`: Content URL
- `output_path`: Directory to save file
- `quality`: Quality preset ('low', 'medium', 'high', 'best')
- `format`: Output format ('mp3', 'mp4', etc.)
- `**kwargs`: Plugin-specific options
  - `quiet`: Suppress output
  - `embed_metadata`: Embed metadata
  - `embed_thumbnail`: Embed thumbnail
  - `proxy`: Proxy URL
  - `rate_limit`: Rate limit string
  - `cookies_file`: Path to cookies
  - `archive_file`: Archive file path
  - `is_playlist`: Download as playlist

**Returns:** Tuple of (success, file_path, error_message)
- `success` (bool): Whether download succeeded
- `file_path` (str, optional): Path to downloaded file
- `error_message` (str, optional): Error description

---

### PluginRegistry Methods

#### `register(plugin_id: str, plugin: BaseConverter) -> None`

Register a new plugin.

```python
registry = get_global_registry()
registry.register('myplatform', MyConverter())
```

---

#### `find_plugin_for_url(url: str) -> Optional[Tuple[str, BaseConverter]]`

Find plugin for URL.

```python
result = registry.find_plugin_for_url('https://youtube.com/watch?v=...')
if result:
    plugin_id, converter = result
```

---

#### `list_plugins() -> Dict[str, PluginCapabilities]`

List all registered plugins.

```python
plugins = registry.list_plugins()
for plugin_id, capabilities in plugins.items():
    print(f"{capabilities.platform}: {capabilities.description}")
```

---

#### `get_plugins_by_content_type(content_type: ContentType) -> Dict[str, BaseConverter]`

Find plugins by content type.

```python
from plugins import ContentType

audio_plugins = registry.get_plugins_by_content_type(ContentType.AUDIO)
```

## Best Practices

### 1. Error Handling

Always implement proper error handling in your `download()` method:

```python
try:
    # Download logic
    return True, file_path, None
except DownloadError as e:
    return False, None, f"Download failed: {str(e)}"
except PermissionError as e:
    return False, None, f"Permission denied: {str(e)}"
except Exception as e:
    return False, None, f"Unexpected error: {str(e)}"
```

### 2. URL Patterns

Be specific with URL patterns to avoid false positives:

```python
url_patterns=[
    r'^https?://(www\.)?platform\.com/video/[\w-]+$',  # More specific
]
```

### 3. Metadata

Provide comprehensive metadata in `get_info()`:

```python
return {
    'title': info.get('title', 'Unknown'),
    'duration': info.get('duration', 0),
    'thumbnail': info.get('thumbnail'),
    'uploader': info.get('uploader', 'Unknown'),
    'description': info.get('description', ''),
    'upload_date': info.get('upload_date'),  # Include more fields
    'is_playlist': is_playlist,
    'video_count': count,
}
```

### 4. Progress Hooks

Implement progress tracking for long downloads:

```python
class ProgressHook:
    def __call__(self, d):
        if d['status'] == 'downloading':
            # Track progress
            pass
        elif d['status'] == 'finished':
            # Download complete
            pass

ydl_opts['progress_hooks'] = [ProgressHook()]
```

### 5. Logging

Support quiet mode:

```python
if not kwargs.get('quiet', False):
    console.print(f"Downloading: {title}")
```

## Testing Plugins

Create tests in `tests/test_plugins.py`:

```python
import pytest
from plugins import get_global_registry

def test_youtube_url_recognition():
    registry = get_global_registry()
    result = registry.find_plugin_for_url('https://youtube.com/watch?v=abc123')
    assert result is not None
    plugin_id, converter = result
    assert plugin_id == 'youtube'

def test_invalid_url():
    registry = get_global_registry()
    result = registry.find_plugin_for_url('https://invalid-domain.com/video')
    assert result is None

def test_capabilities():
    registry = get_global_registry()
    plugin = registry.get_plugin('youtube')
    caps = plugin.capabilities
    assert 'YouTube' in caps.platform
    assert caps.supports_playlist is True
```

## Extending Existing Plugins

To modify an existing plugin, edit its file directly:

```python
# plugins/youtube.py - already exists
class YouTubeConverter(BaseConverter):
    # Modify get_capabilities, download logic, etc.
```

Re-register to apply changes:

```python
registry.register('youtube', YouTubeConverter())
```

## Troubleshooting

### Plugin Not Loading

Check that:
1. Plugin file is in `plugins/` directory
2. Class inherits from `BaseConverter`
3. All required methods are implemented
4. Plugin is registered in `plugins/__init__.py`

### URL Not Recognized

Check that:
1. URL pattern regex is correct
2. Pattern matches your test URL
3. `can_handle()` returns `True`
4. Plugin is registered

### Download Fails

Check that:
1. `get_info()` works first
2. yt-dlp can handle the platform
3. Network is working
4. Output directory is writable
5. FFmpeg is installed for audio conversion

## Examples

See `plugins/` directory for complete implementations of:
- YouTube
- TikTok
- Instagram
- SoundCloud
- Spotify
- Twitch
- Dailymotion
- Vimeo
- Reddit

Each provides a template for implementing new platforms.
