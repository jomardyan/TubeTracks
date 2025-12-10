"""
Smoke tests for YouTube MP3 Downloader
Tests CLI argument parsing, config loading, and basic functionality
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from downloader import (QUALITY_PRESETS, SUPPORTED_FORMATS, Config,
                        DownloadResult, ErrorCode, _parse_rate_limit,
                        check_ffmpeg, check_output_dir, load_config,
                        sanitize_filename, validate_url)


class TestURLValidation:
    """Tests for URL validation"""
    
    def test_valid_youtube_watch_url(self):
        valid, msg = validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert valid is True
        assert msg == ""
    
    def test_valid_youtube_short_url(self):
        valid, msg = validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert valid is True
    
    def test_valid_youtube_playlist_url(self):
        valid, msg = validate_url("https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf")
        assert valid is True
    
    def test_valid_youtube_shorts_url(self):
        valid, msg = validate_url("https://www.youtube.com/shorts/abc123xyz")
        assert valid is True
    
    def test_valid_youtube_music_url(self):
        valid, msg = validate_url("https://music.youtube.com/watch?v=dQw4w9WgXcQ")
        assert valid is True
    
    def test_invalid_url_empty(self):
        valid, msg = validate_url("")
        assert valid is False
        assert "empty" in msg.lower()
    
    def test_valid_vimeo_url(self):
        # Vimeo is now supported via plugin system
        valid, msg = validate_url("https://vimeo.com/123456")
        assert valid is True
    
    def test_invalid_url_malformed(self):
        valid, msg = validate_url("not-a-url")
        assert valid is False
    
    def test_valid_tiktok_url(self):
        # TikTok is supported via plugin system
        valid, msg = validate_url("https://www.tiktok.com/@creator/video/123456789")
        assert valid is True
    
    def test_valid_soundcloud_url(self):
        # SoundCloud is supported via plugin system
        valid, msg = validate_url("https://soundcloud.com/artist/track")
        assert valid is True
    
    def test_invalid_unsupported_platform(self):
        # Unsupported platform should fail
        valid, msg = validate_url("https://totally-fake-platform.xyz/video/123")
        assert valid is False
        assert "Unsupported" in msg or "supported" in msg.lower()


class TestFilenameValidation:
    """Tests for filename sanitization"""
    
    def test_sanitize_normal_filename(self):
        result = sanitize_filename("My Video Title")
        assert result == "My Video Title"
    
    def test_sanitize_removes_unsafe_chars(self):
        result = sanitize_filename("Video: Test <Part 1> \"Quotes\"")
        assert ":" not in result
        assert "<" not in result
        assert ">" not in result
        assert '"' not in result
    
    def test_sanitize_removes_path_separators(self):
        result = sanitize_filename("path/to\\file")
        assert "/" not in result
        assert "\\" not in result
    
    def test_sanitize_long_filename(self):
        long_name = "A" * 300
        result = sanitize_filename(long_name)
        assert len(result) <= 200
    
    def test_sanitize_empty_becomes_untitled(self):
        result = sanitize_filename("")
        assert result == "untitled"
    
    def test_sanitize_only_dots(self):
        result = sanitize_filename("...")
        assert result == "untitled"


class TestRateLimitParsing:
    """Tests for rate limit string parsing"""
    
    def test_parse_kilobytes(self):
        result = _parse_rate_limit("500K")
        assert result == 500 * 1024
    
    def test_parse_megabytes(self):
        result = _parse_rate_limit("1M")
        assert result == 1 * 1024 * 1024
    
    def test_parse_gigabytes(self):
        result = _parse_rate_limit("1G")
        assert result == 1 * 1024 * 1024 * 1024
    
    def test_parse_plain_number(self):
        result = _parse_rate_limit("1000")
        assert result == 1000
    
    def test_parse_lowercase(self):
        result = _parse_rate_limit("500k")
        assert result == 500 * 1024
    
    def test_parse_decimal(self):
        result = _parse_rate_limit("1.5M")
        assert result == int(1.5 * 1024 * 1024)
    
    def test_parse_empty(self):
        result = _parse_rate_limit("")
        assert result is None
    
    def test_parse_none(self):
        result = _parse_rate_limit(None)
        assert result is None
    
    def test_parse_invalid(self):
        result = _parse_rate_limit("abc")
        assert result is None


class TestConfig:
    """Tests for configuration handling"""
    
    def test_config_defaults(self):
        config = Config()
        assert config.quality == 'medium'
        assert config.format == 'mp3'
        assert config.output == './downloads'
        assert config.retries == 3
    
    def test_config_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.conf"
            
            # Create config with custom values
            config = Config(
                quality='high',
                format='flac',
                output='/custom/path',
                retries=5,
                proxy='http://proxy:8080',
            )
            config.save_to_file(config_path)
            
            # Verify file exists
            assert config_path.exists()
            
            # Load config back
            loaded = Config.from_file(config_path)
            assert loaded.quality == 'high'
            assert loaded.format == 'flac'
            assert loaded.output == '/custom/path'
            assert loaded.retries == 5
            assert loaded.proxy == 'http://proxy:8080'


class TestDownloadResult:
    """Tests for DownloadResult dataclass"""
    
    def test_successful_result_str(self):
        result = DownloadResult(
            success=True,
            url="https://youtube.com/watch?v=123",
            title="Test Video"
        )
        assert "✓" in str(result)
        assert "Test Video" in str(result)
    
    def test_failed_result_str(self):
        result = DownloadResult(
            success=False,
            url="https://youtube.com/watch?v=123",
            title="Test Video",
            error_message="Network error"
        )
        assert "✗" in str(result)
        assert "Network error" in str(result)
    
    def test_skipped_result_str(self):
        result = DownloadResult(
            success=True,
            url="https://youtube.com/watch?v=123",
            title="Test Video",
            skipped=True
        )
        assert "⊘" in str(result)
        assert "already downloaded" in str(result)
    
    def test_result_to_dict(self):
        result = DownloadResult(
            success=True,
            url="https://youtube.com/watch?v=123",
            title="Test Video",
            output_path="/path/to/file.mp3",
            attempts=2,
            duration_seconds=10.5
        )
        d = result.to_dict()
        assert d['success'] is True
        assert d['url'] == "https://youtube.com/watch?v=123"
        assert d['title'] == "Test Video"
        assert d['attempts'] == 2
        assert d['duration_seconds'] == 10.5


class TestPreflightChecks:
    """Tests for preflight validation checks"""
    
    def test_check_output_dir_creates_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            new_dir = Path(tmpdir) / "new" / "nested" / "dir"
            valid, msg = check_output_dir(str(new_dir))
            assert valid is True
            assert new_dir.exists()
    
    def test_check_output_dir_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            valid, msg = check_output_dir(tmpdir)
            assert valid is True
    
    def test_check_ffmpeg_available(self):
        # This test assumes ffmpeg is installed in the test environment
        valid, msg = check_ffmpeg()
        # Don't assert on result since ffmpeg may or may not be available
        assert isinstance(valid, bool)
        assert isinstance(msg, str)


class TestQualityPresets:
    """Tests for quality preset constants"""
    
    def test_all_presets_exist(self):
        assert 'low' in QUALITY_PRESETS
        assert 'medium' in QUALITY_PRESETS
        assert 'high' in QUALITY_PRESETS
        assert 'best' in QUALITY_PRESETS
    
    def test_preset_values(self):
        assert QUALITY_PRESETS['low'] == '128'
        assert QUALITY_PRESETS['medium'] == '192'
        assert QUALITY_PRESETS['high'] == '320'
        assert QUALITY_PRESETS['best'] == '0'


class TestSupportedFormats:
    """Tests for supported format constants"""
    
    def test_common_formats_supported(self):
        assert 'mp3' in SUPPORTED_FORMATS
        assert 'm4a' in SUPPORTED_FORMATS
        assert 'flac' in SUPPORTED_FORMATS
        assert 'wav' in SUPPORTED_FORMATS
        assert 'ogg' in SUPPORTED_FORMATS


class TestCLIArgumentParsing:
    """Tests for CLI argument parsing"""
    
    def test_help_does_not_crash(self):
        """Test that --help works without error"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py", "--help"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0
        assert "usage:" in result.stdout.lower()
    
    def test_version_flag(self):
        """Test that --version works"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py", "--version"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0
        assert "1.0.0" in result.stdout or "1.0.0" in result.stderr
    
    def test_show_config(self):
        """Test that --show-config works"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py", "--show-config"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 0
        assert "Quality" in result.stdout or "quality" in result.stdout.lower()
    
    def test_missing_url_shows_error(self):
        """Test that missing URL shows appropriate error"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 2  # EXIT_VALIDATION_ERROR
        assert "error" in result.stdout.lower() or "usage" in result.stdout.lower()


class TestBatchFileHandling:
    """Tests for batch file processing"""
    
    def test_batch_file_not_found(self):
        """Test error handling for missing batch file"""
        import subprocess
        result = subprocess.run(
            [sys.executable, "downloader.py", "-b", "nonexistent_file.txt", "--skip-checks"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )
        assert result.returncode == 2  # EXIT_VALIDATION_ERROR
    
    def test_empty_batch_file(self):
        """Test handling of empty batch file"""
        import subprocess
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("# Only comments\n")
            f.write("# No URLs here\n")
            batch_path = f.name
        
        try:
            result = subprocess.run(
                [sys.executable, "downloader.py", "-b", batch_path, "--skip-checks"],
                capture_output=True,
                text=True,
                cwd=Path(__file__).parent.parent
            )
            # Empty batch file should succeed with warning
            assert result.returncode == 0
            assert "warning" in result.stdout.lower() or "no urls" in result.stdout.lower()
        finally:
            os.unlink(batch_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
