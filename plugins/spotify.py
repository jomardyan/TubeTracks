"""
Spotify converter plugin - extract audio from Spotify tracks/playlists.
Note: Spotify tracks require premium account for direct download via API.
This plugin provides metadata extraction and playlist compilation support.
"""

import re
from typing import Any, Dict, Optional, Tuple

import yt_dlp

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities


class SpotifyConverter(BaseConverter):
    """Spotify track and playlist information extractor"""
    
    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Spotify Converter",
            version="1.0.0",
            platform="Spotify",
            description="Extract metadata from Spotify tracks and create playlists for download",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r'^https?://open\.spotify\.com/track/[\w]+',
                r'^https?://open\.spotify\.com/playlist/[\w]+',
                r'^https?://open\.spotify\.com/album/[\w]+',
                r'^spotify:track:[\w]+',
                r'^spotify:playlist:[\w]+',
            ],
            supported_content_types=[ContentType.AUDIO],
            supports_playlist=True,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=['low', 'medium', 'high', 'best'],
            output_formats=['mp3', 'm4a', 'ogg', 'wav', 'flac'],
        )
    
    def can_handle(self, url: str) -> bool:
        """Check if URL is a Spotify URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate Spotify URL format"""
        if not url:
            return False, "URL cannot be empty"
        
        if self.can_handle(url):
            return True, ""
        
        return False, f"Invalid Spotify URL format: {url}"
    
    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from Spotify URL"""
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
                    'artist': info.get('artist', info.get('uploader', 'Unknown')),
                    'description': info.get('description', ''),
                    'is_playlist': 'entries' in info,
                    'video_count': len(info.get('entries', [])) if 'entries' in info else 1,
                }
        except Exception as e:
            raise RuntimeError(f"Failed to extract Spotify info: {e}")
    
    def download(
        self,
        url: str,
        output_path: str,
        quality: str = 'medium',
        format: str = 'mp3',
        **kwargs
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Download from Spotify.
        Note: Direct download requires authentication or finding equivalent tracks on YouTube.
        """
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
                'noplaylist': not kwargs.get('is_playlist', False),
            }
            
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
            return False, None, f"Spotify download failed: {str(e)}"
