"""GUI lifecycle and queue checks; run under Xvfb on headless Linux."""

import subprocess
import sys
from unittest.mock import patch

import pytest

import downloader


@pytest.mark.parametrize("flag", ["--help", "--version"])
def test_gui_headless_cli(flag):
    result = subprocess.run(
        [sys.executable, "-m", "tubetracks_gui", flag],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    assert "TubeTracks" in result.stdout or "tubetracks-gui" in result.stdout


@pytest.fixture
def app(monkeypatch):
    tk = pytest.importorskip("tkinter")
    import tubetracks_gui

    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"GUI tests need a display (use xvfb-run): {exc}")
    root.withdraw()
    monkeypatch.setattr(downloader, "load_config", downloader.Config)
    instance = tubetracks_gui.App(root)
    yield instance
    try:
        root.destroy()
    except tk.TclError:
        pass


def test_gui_starts_and_collects_defaults(app):
    options = app._collect_options()
    assert options["quality"] == "medium"
    assert options["audio_format"] == "mp3"
    assert options["concurrent_downloads"] == 1
    app.root.update()


def test_preview_worker_sends_complete_metadata(app):
    options = app._collect_options()
    info = {"video_count": 1, "videos": [{"title": "Track"}], "is_playlist": False}
    with patch("downloader.dry_run_info", return_value=info) as preview:
        app._preview_worker("https://youtu.be/test123", options)
    messages = []
    while not app._queue.empty():
        messages.append(app._queue.get_nowait())
    assert any(msg["type"] == "preview_ready" for msg in messages)
    assert messages[-1]["type"] == "preview_complete"
    assert preview.call_args.kwargs["proxy"] == options["proxy"]


def test_worker_reports_result_and_done(app):
    result = downloader.DownloadResult(success=True, title="Track")
    with patch("downloader.download_audio", return_value=result):
        app._run_worker(["https://youtu.be/test123"], app._collect_options())
    messages = []
    while not app._queue.empty():
        messages.append(app._queue.get_nowait())
    assert any(msg["type"] == "result" and msg["result"].success for msg in messages)
    assert messages[-1]["type"] == "done"


def test_close_cancels_background_work(app):
    app._exit_app()
    assert app._cancel_event.is_set()
    assert app._preview_cancel_event.is_set()


def test_worker_honors_concurrent_downloads(app):
    import threading

    barrier = threading.Barrier(2)
    options = app._collect_options()
    options["concurrent_downloads"] = 2

    def download(**kwargs):
        barrier.wait(timeout=5)
        return downloader.DownloadResult(success=True, url=kwargs["url"])

    with patch("downloader.download_audio", side_effect=download):
        app._run_worker(
            ["https://youtu.be/test123", "https://youtu.be/test456"], options
        )
    results = []
    while not app._queue.empty():
        message = app._queue.get_nowait()
        if message["type"] == "result":
            results.append(message["result"])
    assert len(results) == 2
    assert all(result.success for result in results)
