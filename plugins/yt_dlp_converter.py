"""Shared yt-dlp integration for the built-in platform converters."""

from pathlib import Path
from typing import Any

import yt_dlp
from yt_dlp.utils import DownloadError

AUDIO_CODECS = {
    "mp3": "mp3",
    "m4a": "m4a",
    "flac": "flac",
    "wav": "wav",
    "ogg": "vorbis",
    "vorbis": "vorbis",
    "opus": "opus",
}
THUMBNAIL_FORMATS = {"mp3", "m4a", "flac", "ogg", "vorbis", "opus", "mp4"}
BITRATES = {"low": "128", "medium": "192", "high": "320", "best": "0"}


def network_options(options: dict[str, Any]) -> dict[str, Any]:
    """Translate public network options to yt-dlp's Python API."""
    result = {}
    for source, target in (("proxy", "proxy"), ("cookies_file", "cookiefile")):
        if options.get(source):
            result[target] = options[source]
    limit = options.get("rate_limit")
    if limit is not None and limit != "":
        if isinstance(limit, str):
            limit = yt_dlp.utils.parse_bytes(limit.strip())
        if limit is None or limit <= 0:
            raise ValueError("Rate limit must be a positive number, such as 500K or 1M")
        result["ratelimit"] = limit
    return result


class YtDlpConverter:
    """Reusable metadata, conversion and progress behavior for platform plugins.

    Platform classes also inherit BaseConverter to supply their capabilities and
    URL matching. Keeping this adapter separate avoids circular imports.
    """

    def get_info(self, url: str, **kwargs) -> dict[str, Any]:
        options = {
            "quiet": True,
            "no_warnings": True,
            "noplaylist": not kwargs.get("is_playlist", False),
            "extract_flat": "in_playlist" if kwargs.get("is_playlist") else False,
            **network_options(kwargs),
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise ValueError("No media information returned")
                info = dict(info)
                is_playlist = "entries" in info
                if is_playlist:
                    # yt-dlp may return a lazy iterable, including unavailable entries.
                    info["entries"] = [
                        entry for entry in info.get("entries") or [] if entry
                    ]
                info["is_playlist"] = is_playlist
                info["video_count"] = len(info["entries"]) if is_playlist else 1
            return info
        except Exception as exc:
            raise RuntimeError(
                f"Failed to extract {self.capabilities.platform} info: {exc}"
            ) from exc

    def download(
        self,
        url: str,
        output_path: str,
        quality: str = "medium",
        format: str = "mp3",
        **kwargs,
    ) -> tuple[bool, str | None, str | None]:
        """Convert media and report the path after all postprocessors finish."""
        platform = self.capabilities.platform
        try:
            if quality not in BITRATES:
                raise ValueError(f"Unsupported quality: {quality}")
            if format not in AUDIO_CODECS and format != "mp4":
                raise ValueError(f"Unsupported format: {format}")

            cancel_event = kwargs.get("cancel_event")

            def check_cancelled():
                if cancel_event and cancel_event.is_set():
                    raise DownloadError("Download cancelled by user")

            check_cancelled()
            output_dir = Path(output_path).expanduser()
            output_dir.mkdir(parents=True, exist_ok=True)
            template = kwargs.get("filename_template", "%(title)s.%(ext)s")
            postprocessors = []
            if format == "mp4":
                postprocessors.append(
                    {"key": "FFmpegVideoRemuxer", "preferedformat": "mp4"}
                )
            else:
                postprocessors.append(
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": AUDIO_CODECS[format],
                        "preferredquality": BITRATES[quality],
                    }
                )
            if kwargs.get("embed_metadata", True):
                postprocessors.append({"key": "FFmpegMetadata"})
            thumbnail = (
                kwargs.get("embed_thumbnail", True) and format in THUMBNAIL_FORMATS
            )
            if thumbnail:
                postprocessors.append({"key": "EmbedThumbnail"})

            progress_hook = kwargs.get("progress_hook") or kwargs.get(
                "progress_callback"
            )
            downloaded_file = None
            any_downloaded = False

            def progress(payload):
                nonlocal any_downloaded
                check_cancelled()
                if payload.get("status") == "finished":
                    any_downloaded = True
                if progress_hook:
                    progress_hook(payload)

            def postprocess_progress(payload):
                check_cancelled()
                if progress_hook:
                    progress_hook(payload)

            def finished(filename):
                nonlocal downloaded_file, any_downloaded
                check_cancelled()
                # post_hooks run after conversion and MoveFilesAfterDownload.
                downloaded_file = filename
                any_downloaded = True

            options = {
                "format": (
                    "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
                    if format == "mp4"
                    else "bestaudio/best"
                ),
                "postprocessors": postprocessors,
                "outtmpl": str(output_dir / template),
                "quiet": kwargs.get("quiet", False),
                "no_warnings": kwargs.get("quiet", False),
                "noprogress": kwargs.get("quiet", False),
                "writethumbnail": thumbnail,
                "noplaylist": not kwargs.get("is_playlist", False),
                "continuedl": True,
                "progress_hooks": [progress],
                "postprocessor_hooks": [postprocess_progress],
                "post_hooks": [finished],
                **network_options(kwargs),
            }
            if format == "mp4":
                options["merge_output_format"] = "mp4"
            if kwargs.get("archive_file"):
                options["download_archive"] = str(
                    Path(kwargs["archive_file"]).expanduser()
                )
            if kwargs.get("skip_existing"):
                options["overwrites"] = False
            if kwargs.get("max_retries") is not None:
                retries = max(0, int(kwargs["max_retries"]))
                options["retries"] = retries
                options["fragment_retries"] = retries

            # Use yt-dlp's maintained defaults for YouTube clients, HTTP headers
            # and JavaScript challenges rather than hard-coded legacy clients.
            with yt_dlp.YoutubeDL(options) as ydl:
                status = ydl.download([url])
            check_cancelled()
            if status:
                raise DownloadError(f"yt-dlp exited with status {status}")
            if not any_downloaded:
                return (
                    False,
                    None,
                    "Skipped: no new files downloaded (already in archive).",
                )
            return True, downloaded_file, None
        except Exception as exc:
            return False, None, f"{platform} download failed: {exc}"
