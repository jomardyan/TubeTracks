"""Regression tests for the yt-dlp adapter and downloader lifecycle."""

import threading
from unittest.mock import MagicMock, patch

import pytest

import downloader
from plugins import get_global_registry
from plugins.yt_dlp_converter import AUDIO_CODECS, network_options

URL = "https://www.youtube.com/watch?v=test123"
CONVERTERS = list(get_global_registry())


@pytest.mark.parametrize(
    "plugin_id,converter", CONVERTERS, ids=[p[0] for p in CONVERTERS]
)
@pytest.mark.parametrize("audio_format", list(AUDIO_CODECS) + ["mp4"])
def test_conversion_contract(plugin_id, converter, audio_format, tmp_path):
    """Every platform must honor the selected codec and final output path."""
    final_path = str(tmp_path / "converted.mp4")
    events = []
    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL") as factory:

        def download(urls):
            assert urls == [URL]
            opts = factory.call_args.args[0]
            opts["progress_hooks"][0]({"status": "finished", "filename": "source.webm"})
            opts["postprocessor_hooks"][0](
                {"status": "finished", "postprocessor": "ExtractAudio"}
            )
            opts["post_hooks"][0](final_path)
            return 0

        factory.return_value.__enter__.return_value.download.side_effect = download
        result = converter.download(
            URL,
            str(tmp_path),
            format=audio_format,
            quality="high",
            quiet=True,
            progress_hook=events.append,
            proxy="http://proxy:8080",
            rate_limit="1M",
            cookies_file="cookies.txt",
            archive_file=str(tmp_path / "archive.txt"),
            max_retries=2,
            skip_existing=True,
            is_playlist=True,
        )
        opts = factory.call_args.args[0]
    assert result == (True, final_path, None)
    assert opts["ratelimit"] == 1024**2
    assert opts["cookiefile"] == "cookies.txt"
    assert opts["proxy"] == "http://proxy:8080"
    assert opts["download_archive"] == str(tmp_path / "archive.txt")
    assert opts["retries"] == opts["fragment_retries"] == 2
    assert opts["overwrites"] is False
    assert opts["noplaylist"] is False
    assert "extractor_args" not in opts
    assert "http_headers" not in opts
    first_pp = opts["postprocessors"][0]
    if audio_format == "mp4":
        assert first_pp == {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
    else:
        assert first_pp["preferredcodec"] == AUDIO_CODECS[audio_format]
        assert first_pp["preferredquality"] == "320"
    assert opts["writethumbnail"] is (audio_format != "wav")
    assert len(events) == 2


@pytest.mark.parametrize(
    "plugin_id,converter", CONVERTERS, ids=[p[0] for p in CONVERTERS]
)
def test_lazy_playlist_metadata(plugin_id, converter):
    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL") as factory:
        factory.return_value.__enter__.return_value.extract_info.return_value = {
            "title": "Playlist",
            "entries": iter([{"title": "One"}, None, {"title": "Two"}]),
        }
        info = converter.get_info(URL, is_playlist=True, cookies_file="auth.txt")
        opts = factory.call_args.args[0]
    assert info["is_playlist"] is True
    assert info["video_count"] == 2
    assert [item["title"] for item in info["entries"]] == ["One", "Two"]
    assert opts["extract_flat"] == "in_playlist"
    assert opts["cookiefile"] == "auth.txt"


def test_archived_download_is_skipped(tmp_path):
    converter = CONVERTERS[0][1]
    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL") as factory:
        factory.return_value.__enter__.return_value.download.return_value = 0
        success, path, error = converter.download(URL, str(tmp_path))
    assert not success
    assert path is None
    assert "Skipped" in error


def test_failed_download_does_not_look_skipped(tmp_path):
    converter = CONVERTERS[0][1]
    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL") as factory:
        factory.return_value.__enter__.return_value.download.return_value = 1
        success, path, error = converter.download(URL, str(tmp_path))
    assert not success
    assert path is None
    assert "status 1" in error


@pytest.mark.parametrize("limit", ["garbage", "0", "-1", -1, 0])
def test_invalid_rate_limits(limit):
    with pytest.raises(ValueError, match="Rate limit"):
        network_options({"rate_limit": limit})


@pytest.fixture
def fake_converter(monkeypatch):
    converter = MagicMock()
    registry = MagicMock()
    registry.find_plugin_for_url.return_value = ("test", converter)
    monkeypatch.setattr(downloader, "get_global_registry", lambda: registry)
    monkeypatch.setattr(downloader, "check_ffmpeg", lambda: (True, ""))
    return converter


def test_download_retries_and_returns_final_file(fake_converter, tmp_path):
    output = tmp_path / "Track.mp3"
    output.write_bytes(b"audio")
    fake_converter.download.side_effect = [
        (False, None, "Connection reset"),
        (True, str(output), None),
    ]
    result = downloader.download_audio(
        URL, output_dir=str(tmp_path), max_retries=2, retry_delay=0
    )
    assert result.success
    assert result.attempts == 2
    assert result.title == "Track"
    assert result.output_path == str(output)
    assert result.file_size == 5


def test_nonretryable_error(fake_converter, tmp_path):
    fake_converter.download.return_value = (False, None, "HTTP Error 403: Forbidden")
    result = downloader.download_audio(URL, output_dir=str(tmp_path), max_retries=3)
    assert result.error_code == downloader.ErrorCode.PERMISSION_ERROR
    assert result.attempts == 1


def test_cancel_during_retry_wait(fake_converter, tmp_path):
    event = threading.Event()

    def fail(*args, **kwargs):
        event.set()
        return False, None, "Connection reset"

    fake_converter.download.side_effect = fail
    result = downloader.download_audio(
        URL, output_dir=str(tmp_path), max_retries=3, retry_delay=10, cancel_event=event
    )
    assert result.error_code == downloader.ErrorCode.CANCELLED
    assert result.attempts == 1


def test_pre_cancel_does_not_create_output(tmp_path):
    event = threading.Event()
    event.set()
    output = tmp_path / "unused"
    result = downloader.download_audio(URL, output_dir=str(output), cancel_event=event)
    assert result.error_code == downloader.ErrorCode.CANCELLED
    assert not output.exists()


def test_cancel_during_postprocessing(tmp_path):
    event = threading.Event()
    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL") as factory:

        def download(urls):
            event.set()
            factory.call_args.args[0]["postprocessor_hooks"][0]({"status": "started"})

        factory.return_value.__enter__.return_value.download.side_effect = download
        success, _, error = CONVERTERS[0][1].download(
            URL, str(tmp_path), cancel_event=event
        )
    assert not success
    assert "cancelled" in error.lower()


@pytest.mark.parametrize(
    "name,stage",
    [
        ("ExtractAudio", "converting"),
        ("Metadata", "metadata"),
        ("EmbedThumbnail", "thumbnail"),
    ],
)
def test_current_postprocessor_names(name, stage):
    payload = downloader._normalize_progress_payload(
        {"status": "started", "postprocessor": name}
    )
    assert payload["stage"] == stage
    assert payload["status"] == "processing"


def test_preview_resolves_template_and_unavailable_entries(fake_converter, tmp_path):
    fake_converter.get_info.return_value = {
        "title": "Collection",
        "entries": [None, {"title": "Track", "artist": "Artist", "id": "123"}],
    }
    info = downloader.dry_run_info(
        URL,
        output_dir=str(tmp_path),
        audio_format="flac",
        filename_template="%(artist)s - %(title)s.%(ext)s",
        is_playlist=True,
    )
    assert info["video_count"] == 1
    assert info["playlist_title"] == "Collection"
    assert info["videos"][0]["resolved_path"] == str(tmp_path / "Artist - Track.flac")


def test_preview_single_video(fake_converter, tmp_path):
    fake_converter.get_info.return_value = {
        "title": "Track",
        "id": "123",
        "duration": 10,
    }
    info = downloader.dry_run_info(URL, output_dir=str(tmp_path))
    assert info["video_count"] == 1
    assert info["videos"][0]["title"] == "Track"


def test_progress_callback_receives_postprocessing(fake_converter, tmp_path):
    events = []

    def download(*args, **kwargs):
        kwargs["progress_hook"]({"status": "started", "postprocessor": "ExtractAudio"})
        return True, None, None

    fake_converter.download.side_effect = download
    result = downloader.download_audio(
        URL, output_dir=str(tmp_path), progress_callback=events.append
    )
    assert result.success
    assert events[0]["stage"] == "converting"


def test_config_unicode_roundtrip(tmp_path):
    path = tmp_path / "settings.conf"
    config = downloader.Config(
        output="音楽/Музыка", template="%(artist)s - %(title)s.%(ext)s"
    )
    config.save_to_file(path)
    assert downloader.Config.from_file(path) == config
