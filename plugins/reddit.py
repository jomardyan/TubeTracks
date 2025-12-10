"""
Reddit converter plugin - download videos and audio from Reddit.
"""

import re
from typing import Any, Dict, Optional, Tuple

import yt_dlp

from .base import BaseConverter, ContentType, ExtractorType, PluginCapabilities


class RedditConverter(BaseConverter):
    """Reddit video and audio downloader"""
    
    def get_capabilities(self) -> PluginCapabilities:
        return PluginCapabilities(
            name="Reddit Converter",
            version="1.0.0",
            platform="Reddit",
            description="Download videos and audio from Reddit posts",
            author="YouTube MP3 Downloader",
            url_patterns=[
                r'^https?://(www\.)?reddit\.com/r/[\w]+/comments/[\w]+',
                r'^https?://reddit\.com/r/[\w]+/comments/[\w]+',
                r'^https?://(www\.)?reddit\.com/user/[\w]+',
            ],
            supported_content_types=[ContentType.AUDIO, ContentType.VIDEO],
            supports_playlist=False,
            supports_auth=False,
            supports_subtitles=False,
            supports_metadata=True,
            extractor_type=ExtractorType.YT_DLP,
            quality_presets=['low', 'medium', 'high'],
            output_formats=['mp3', 'mp4', 'm4a'],
        )
    
    def can_handle(self, url: str) -> bool:
        """Check if URL is a Reddit URL"""
        for pattern in self.capabilities.url_patterns:
            if re.match(pattern, url, re.IGNORECASE):
                return True
        return False
    
    def validate_url(self, url: str) -> Tuple[bool, str]:
        """Validate Reddit URL format"""
        if not url:
            return False, "URL cannot be empty"
        
        if self.can_handle(url):
            return True, ""
        
        return False, f"Invalid Reddit URL format: {url}"
    
    def get_info(self, url: str, **kwargs) -> Dict[str, Any]:
        """Extract metadata from Reddit URL"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', 'Unknown'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail', None),
                    'uploader': info.get('uploader', 'Unknown'),
                    'description': info.get('description', ''),
                    'upvotes': info.get('upvotes', 0),
                    'comment_count': info.get('comment_count', 0),
                    'is_playlist': False,
                    'video_count': 1,
                }
        except Exception as e:
            raise RuntimeError(f"Failed to extract Reddit info: {e}")
    
    def download(
        self,
        url: str,
        output_path: str,
        quality: str = 'medium',
        format: str = 'mp3',
        **kwargs
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Download and convert Reddit content"""
        try:
            from pathlib import Path
            
            Path(output_path).mkdir(parents=True, exist_ok=True)
            
            bitrates = {
                'low': '128',
                'medium': '192',
                'high': '320',
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
            return False, None, f"Reddit download failed: {str(e)}"
