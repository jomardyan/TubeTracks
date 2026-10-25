"""Run real yt-dlp and FFmpeg against generated media served on loopback."""

import base64
import functools
import json
import shutil
import subprocess
import threading
import wave
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import pytest
import yt_dlp
from yt_dlp.extractor.common import InfoExtractor

import downloader
from plugins import get_global_registry


@pytest.fixture(scope="module")
def media_server(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Media integration tests require FFmpeg and ffprobe")
    source = tmp_path_factory.mktemp("media-source")
    with wave.open(str(source / "sample.wav"), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(44100)
        output.writeframes(b"\0\0" * 22050)
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=blue:s=32x32:d=0.5",
            "-i",
            str(source / "sample.wav"),
            "-c:v",
            "mpeg4",
            "-c:a",
            "aac",
            "-shortest",
            str(source / "sample.mp4"),
        ],
        check=True,
        timeout=30,
    )
    (source / "cover.png").write_bytes(
        base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
        )
    )

    class Handler(SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=str(source))
    )
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)


@pytest.fixture
def local_extractor(media_server):
    """Replace only platform extraction; exercise the installed download pipeline."""

    class FixtureIE(InfoExtractor):
        _VALID_URL = r"https://www\.youtube\.com/watch\?v=fixture_(?P<id>audio|video)"

        def _real_extract(self, url):
            media_id = self._match_id(url)
            video = media_id == "video"
            return {
                "id": media_id,
                "title": "Fixture Track",
                "artist": "Fixture Artist",
                "url": f"{media_server}/sample.{'mp4' if video else 'wav'}",
                "ext": "mp4" if video else "wav",
                "vcodec": "mpeg4" if video else "none",
                "acodec": "aac" if video else "pcm_s16le",
                "thumbnail": f"{media_server}/cover.png",
            }

    original = yt_dlp.YoutubeDL

    class LocalYoutubeDL(original):
        def __init__(self, params=None):
            super().__init__(params, auto_init=False)
            self.add_info_extractor(FixtureIE())
            self.add_default_info_extractors()

    with patch("plugins.yt_dlp_converter.yt_dlp.YoutubeDL", LocalYoutubeDL):
        yield


@pytest.mark.parametrize(
    "audio_format,extension,codec",
    [
        ("mp3", "mp3", "mp3"),
        ("m4a", "m4a", "aac"),
        ("flac", "flac", "flac"),
        ("wav", "wav", "pcm_s16le"),
        ("ogg", "ogg", "vorbis"),
        ("vorbis", "ogg", "vorbis"),
        ("opus", "opus", "opus"),
        ("mp4", "mp4", "aac"),
    ],
)
def test_real_conversion(local_extractor, tmp_path, audio_format, extension, codec):
    kind = "video" if audio_format == "mp4" else "audio"
    result = downloader.download_audio(
        f"https://www.youtube.com/watch?v=fixture_{kind}",
        output_dir=str(tmp_path),
        audio_format=audio_format,
        quiet=True,
    )
    assert result.success, result.error_message
    from pathlib import Path

    output = Path(result.output_path)
    assert output.suffix == f".{extension}"
    assert output.is_file()
    assert result.file_size > 0
    probe = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    metadata = json.loads(probe.stdout)
    assert any(stream.get("codec_name") == codec for stream in metadata["streams"])
    tags = {
        key.casefold(): value
        for section in [
            metadata["format"],
            *(
                stream
                for stream in metadata["streams"]
                if stream["codec_type"] == "audio"
            ),
        ]
        for key, value in section.get("tags", {}).items()
    }
    assert tags["title"] == "Fixture Track"
    if audio_format == "mp4":
        assert any(s["codec_type"] == "video" for s in metadata["streams"])


@pytest.mark.parametrize(
    "plugin_id,converter",
    list(get_global_registry()),
    ids=[p[0] for p in get_global_registry()],
)
def test_each_plugin_downloads_with_real_backend(
    local_extractor, tmp_path, plugin_id, converter
):
    success, path, error = converter.download(
        "https://www.youtube.com/watch?v=fixture_audio",
        str(tmp_path),
        quiet=True,
        embed_thumbnail=False,
    )
    assert success, error
    assert path.endswith(".mp3")


def test_real_archive_skips_second_download(local_extractor, tmp_path):
    options = dict(
        output_dir=str(tmp_path), quiet=True, archive_file=str(tmp_path / "archive.txt")
    )
    first = downloader.download_audio(
        "https://www.youtube.com/watch?v=fixture_audio", **options
    )
    second = downloader.download_audio(
        "https://www.youtube.com/watch?v=fixture_audio", **options
    )
    assert first.success, first.error_message
    assert second.success
    assert second.skipped
