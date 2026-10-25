"""CLI tests exercise settings, batch input and preview without external services."""

from unittest.mock import patch

import pytest

import downloader

URL = "https://www.youtube.com/watch?v=test123"


@pytest.fixture(autouse=True)
def isolated_config(monkeypatch, tmp_path):
    monkeypatch.setattr(downloader, "DEFAULT_CONFIG_FILE", tmp_path / "default.conf")


def test_batch_file_not_found(tmp_path):
    assert downloader.main(["-b", str(tmp_path / "missing.txt")]) == 2


def test_empty_batch_file(tmp_path):
    batch = tmp_path / "empty.txt"
    batch.write_text("# Only a comment\n\n", encoding="utf-8")
    assert downloader.main(["-b", str(batch)]) == 2


def test_batch_urls_and_config_overrides(tmp_path):
    config_path = tmp_path / "settings.conf"
    downloader.Config(
        quality="high", format="flac", output="saved", concurrent_downloads=2
    ).save_to_file(config_path)
    batch = tmp_path / "urls.txt"
    batch.write_text(f"\ufeff# Comment\n{URL}\n\n{URL}&t=1\n", encoding="utf-8")
    with patch(
        "downloader.download_audio",
        return_value=downloader.DownloadResult(success=True),
    ) as download:
        assert (
            downloader.main(
                [
                    "-b",
                    str(batch),
                    "--config",
                    str(config_path),
                    "-f",
                    "wav",
                    "--no-use-archive",
                ]
            )
            == 0
        )
    assert download.call_count == 2
    opts = download.call_args.kwargs
    assert opts["quality"] == "high"
    assert opts["audio_format"] == "wav"
    assert opts["output_dir"] == "saved"
    assert opts["archive_file"] is None


def test_dry_run_does_not_download_or_create_output(tmp_path):
    output = tmp_path / "unused"
    with (
        patch(
            "downloader.dry_run_info", return_value={"videos": [{"title": "Track"}]}
        ) as preview,
        patch("downloader.download_audio") as download,
    ):
        assert (
            downloader.main(
                [
                    URL,
                    "--dry-run",
                    "-o",
                    str(output),
                    "-p",
                    "--proxy",
                    "http://proxy:8080",
                ]
            )
            == 0
        )
    download.assert_not_called()
    assert preview.call_args.kwargs["is_playlist"] is True
    assert preview.call_args.kwargs["proxy"] == "http://proxy:8080"
    assert not output.exists()


def test_failed_download_exit_code():
    with patch(
        "downloader.download_audio",
        return_value=downloader.DownloadResult(success=False),
    ):
        assert downloader.main([URL, "--retries", "0"]) == 1


def test_save_config(tmp_path):
    path = tmp_path / "settings.conf"
    assert downloader.main(["--config", str(path), "--save-config", "-q", "high"]) == 0
    assert downloader.Config.from_file(path).quality == "high"
