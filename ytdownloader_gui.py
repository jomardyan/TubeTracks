"""Tkinter GUI frontend for AudioDownload-YT.

This file intentionally keeps the CLI in downloader.py untouched.
It uses downloader.py as a backend and adds a simple desktop UI.

Run:
  python ytdownloader_gui.py
"""

from __future__ import annotations

import queue
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import downloader


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"YouTube MP3 Downloader (GUI) v{downloader.__version__}")
        self.root.minsize(860, 620)

        self._worker: Optional[threading.Thread] = None
        self._cancel_event = threading.Event()
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()

        self._build_menu()
        self._build_ui()
        self._setup_shortcuts()
        self._poll_queue()

    def _build_menu(self) -> None:
        """Build the menu bar with File, Edit, and Help menus."""
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(
            label="Open URLs from file...",
            command=self._open_urls_file,
            accelerator="Ctrl+O",
        )
        file_menu.add_command(
            label="Save Log...", command=self._save_log, accelerator="Ctrl+S"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Clear URLs", command=self._clear_urls)
        file_menu.add_command(label="Clear Log", command=self._clear_log)
        file_menu.add_separator()
        file_menu.add_command(
            label="Exit", command=self._exit_app, accelerator="Alt+F4"
        )

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(
            label="Cut", command=lambda: self._edit_command("cut"), accelerator="Ctrl+X"
        )
        edit_menu.add_command(
            label="Copy",
            command=lambda: self._edit_command("copy"),
            accelerator="Ctrl+C",
        )
        edit_menu.add_command(
            label="Paste",
            command=lambda: self._edit_command("paste"),
            accelerator="Ctrl+V",
        )
        edit_menu.add_command(
            label="Select All",
            command=lambda: self._edit_command("select_all"),
            accelerator="Ctrl+A",
        )

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _setup_shortcuts(self) -> None:
        """Setup keyboard shortcuts."""
        self.root.bind("<Control-o>", lambda e: self._open_urls_file())
        self.root.bind("<Control-s>", lambda e: self._save_log())

    def _create_context_menu(self, widget: tk.Text) -> tk.Menu:
        """Create a context menu for text widgets with cut/copy/paste."""
        menu = tk.Menu(widget, tearoff=0)
        menu.add_command(
            label="Cut", command=lambda: self._text_cut(widget), accelerator="Ctrl+X"
        )
        menu.add_command(
            label="Copy", command=lambda: self._text_copy(widget), accelerator="Ctrl+C"
        )
        menu.add_command(
            label="Paste",
            command=lambda: self._text_paste(widget),
            accelerator="Ctrl+V",
        )
        menu.add_separator()
        menu.add_command(
            label="Select All",
            command=lambda: self._text_select_all(widget),
            accelerator="Ctrl+A",
        )

        def show_menu(event):
            try:
                menu.tk_popup(event.x_root, event.y_root)
            finally:
                menu.grab_release()

        widget.bind("<Button-3>", show_menu)
        return menu

    def _text_cut(self, widget: tk.Text) -> None:
        """Cut text from widget."""
        try:
            widget.event_generate("<<Cut>>")
        except tk.TclError:
            pass

    def _text_copy(self, widget: tk.Text) -> None:
        """Copy text from widget."""
        try:
            widget.event_generate("<<Copy>>")
        except tk.TclError:
            pass

    def _text_paste(self, widget: tk.Text) -> None:
        """Paste text into widget."""
        try:
            widget.event_generate("<<Paste>>")
        except tk.TclError:
            pass

    def _text_select_all(self, widget: tk.Text) -> None:
        """Select all text in widget."""
        widget.tag_add("sel", "1.0", "end")
        widget.mark_set("insert", "1.0")
        widget.see("insert")
        return "break"

    def _edit_command(self, command: str) -> None:
        """Execute edit command on focused widget."""
        focused = self.root.focus_get()
        if focused:
            if command == "cut":
                self._text_cut(focused)
            elif command == "copy":
                self._text_copy(focused)
            elif command == "paste":
                self._text_paste(focused)
            elif command == "select_all":
                self._text_select_all(focused)

    def _open_urls_file(self) -> None:
        """Open a text file containing URLs."""
        filename = filedialog.askopenfilename(
            title="Open URLs file",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if filename:
            try:
                with open(filename, "r", encoding="utf-8") as f:
                    content = f.read()
                self.urls_text.delete("1.0", "end")
                self.urls_text.insert("1.0", content)
                self._append_log(f"Loaded URLs from: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open file: {e}")

    def _save_log(self) -> None:
        """Save the log to a file."""
        filename = filedialog.asksaveasfilename(
            title="Save log",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if filename:
            try:
                content = self.log_text.get("1.0", "end")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)
                messagebox.showinfo("Success", f"Log saved to: {filename}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save log: {e}")

    def _clear_urls(self) -> None:
        """Clear the URLs text box."""
        if messagebox.askyesno("Clear URLs", "Clear all URLs?"):
            self.urls_text.delete("1.0", "end")

    def _clear_log(self) -> None:
        """Clear the log text box."""
        if messagebox.askyesno("Clear Log", "Clear the log?"):
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")

    def _show_about(self) -> None:
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            f"YouTube MP3 Downloader (GUI)\n"
            f"Version {downloader.__version__}\n\n"
            f"A multi-platform audio downloader with plugin support.\n"
            f"Supports YouTube, Spotify, SoundCloud, and more.",
        )

    def _exit_app(self) -> None:
        """Exit the application."""
        if self._worker and self._worker.is_alive():
            if messagebox.askyesno("Exit", "Download in progress. Exit anyway?"):
                self._cancel_event.set()
                self.root.quit()
        else:
            self.root.quit()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(4, weight=1)

        # URLs
        ttk.Label(outer, text="URLs (one per line)").grid(row=0, column=0, sticky="w")
        self.urls_text = tk.Text(outer, height=7, wrap="word")
        self.urls_text.grid(row=1, column=0, sticky="nsew", pady=(6, 10))
        self._create_context_menu(self.urls_text)

        # Options row
        options = ttk.Frame(outer)
        options.grid(row=2, column=0, sticky="ew")
        for i in range(8):
            options.columnconfigure(i, weight=0)
        options.columnconfigure(1, weight=1)
        options.columnconfigure(6, weight=1)

        ttk.Label(options, text="Output folder").grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "downloads"))
        self.output_entry = ttk.Entry(options, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        ttk.Button(options, text="Browse…", command=self._choose_output).grid(
            row=0, column=2, sticky="w"
        )

        ttk.Label(options, text="Quality").grid(
            row=0, column=3, sticky="w", padx=(14, 0)
        )
        self.quality_var = tk.StringVar(value="medium")
        self.quality_combo = ttk.Combobox(
            options,
            textvariable=self.quality_var,
            values=["low", "medium", "high", "best"],
            width=10,
            state="readonly",
        )
        self.quality_combo.grid(row=0, column=4, sticky="w", padx=(8, 8))

        ttk.Label(options, text="Format").grid(row=0, column=5, sticky="w")
        self.format_var = tk.StringVar(value="mp3")
        self.format_combo = ttk.Combobox(
            options,
            textvariable=self.format_var,
            values=list(downloader.SUPPORTED_FORMATS),
            width=10,
            state="readonly",
        )
        self.format_combo.grid(row=0, column=6, sticky="w", padx=(8, 0))

        # Secondary options
        options2 = ttk.Frame(outer)
        options2.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        for i in range(14):
            options2.columnconfigure(i, weight=0)
        options2.columnconfigure(11, weight=1)

        self.playlist_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            options2, text="Treat as playlist", variable=self.playlist_var
        ).grid(row=0, column=0, sticky="w")

        self.metadata_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options2, text="Embed metadata", variable=self.metadata_var
        ).grid(row=0, column=1, sticky="w", padx=(14, 0))

        self.thumbnail_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options2, text="Embed thumbnail", variable=self.thumbnail_var
        ).grid(row=0, column=2, sticky="w", padx=(14, 0))

        self.skip_existing_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options2, text="Skip existing", variable=self.skip_existing_var
        ).grid(row=0, column=3, sticky="w", padx=(14, 0))

        ttk.Label(options2, text="Concurrent").grid(
            row=0, column=4, sticky="w", padx=(14, 0)
        )
        self.concurrent_var = tk.IntVar(value=3)
        self.concurrent_spin = ttk.Spinbox(
            options2, from_=1, to=5, textvariable=self.concurrent_var, width=5
        )
        self.concurrent_spin.grid(row=0, column=5, sticky="w", padx=(8, 0))

        ttk.Label(options2, text="Retries").grid(
            row=0, column=6, sticky="w", padx=(14, 0)
        )
        self.retries_var = tk.IntVar(value=3)
        self.retries_spin = ttk.Spinbox(
            options2, from_=0, to=20, textvariable=self.retries_var, width=5
        )
        self.retries_spin.grid(row=0, column=7, sticky="w", padx=(8, 0))

        self.use_archive_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            options2, text="Use archive", variable=self.use_archive_var
        ).grid(row=0, column=8, sticky="w", padx=(14, 0))

        ttk.Label(options2, text="Archive file").grid(
            row=0, column=9, sticky="w", padx=(14, 0)
        )
        self.archive_var = tk.StringVar(value=str(downloader.DEFAULT_ARCHIVE_FILE))
        self.archive_entry = ttk.Entry(
            options2, textvariable=self.archive_var, width=22
        )
        self.archive_entry.grid(row=0, column=10, sticky="w", padx=(8, 8))

        ttk.Label(options2, text="Template").grid(row=0, column=11, sticky="w")
        self.template_var = tk.StringVar(value="%(title)s.%(ext)s")
        self.template_entry = ttk.Entry(
            options2, textvariable=self.template_var, width=20
        )
        self.template_entry.grid(row=0, column=12, sticky="w", padx=(8, 0))

        # Log area
        ttk.Label(outer, text="Log").grid(row=4, column=0, sticky="w")
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=5, column=0, sticky="nsew", pady=(6, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        self.log_text = tk.Text(log_frame, height=12, wrap="word", state="disabled")
        self.log_text.grid(row=0, column=0, sticky="nsew")
        scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set)
        self._create_context_menu(self.log_text)

        # Progress + controls
        bottom = ttk.Frame(outer)
        bottom.grid(row=6, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(bottom, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )

        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        controls = ttk.Frame(bottom)
        controls.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        self.start_btn = ttk.Button(controls, text="Start", command=self._start)
        self.start_btn.grid(row=0, column=0, padx=(0, 8))

        self.cancel_btn = ttk.Button(
            controls, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_btn.grid(row=0, column=1)

    def _choose_output(self) -> None:
        folder = filedialog.askdirectory(title="Choose output folder")
        if folder:
            self.output_var.set(folder)

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        """Enable or disable controls based on running state."""
        state_normal = "normal" if not running else "disabled"
        state_readonly = "readonly" if not running else "disabled"

        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.urls_text.configure(state=state_normal)
        self.output_entry.configure(state=state_normal)
        self.quality_combo.configure(state=state_readonly)
        self.format_combo.configure(state=state_readonly)
        self.template_entry.configure(state=state_normal)
        self.archive_entry.configure(state=state_normal)
        self.retries_spin.configure(state=state_normal)

    def _validate_inputs(self) -> Optional[List[str]]:
        urls_raw = self.urls_text.get("1.0", "end").strip()
        if not urls_raw:
            messagebox.showerror("Missing URLs", "Please paste at least one URL.")
            return None

        urls = [
            u.strip()
            for u in urls_raw.splitlines()
            if u.strip() and not u.strip().startswith("#")
        ]
        if not urls:
            messagebox.showerror("Missing URLs", "No valid URLs found.")
            return None

        output_dir = self.output_var.get().strip()
        if not output_dir:
            messagebox.showerror(
                "Missing output folder", "Please choose an output folder."
            )
            return None

        # GUI-friendly checks (no Rich output)
        ff_ok, ff_msg = downloader.check_ffmpeg()
        if not ff_ok:
            messagebox.showerror("FFmpeg not found", ff_msg)
            return None

        dir_ok, dir_msg = downloader.check_output_dir(output_dir)
        if not dir_ok:
            messagebox.showerror("Output folder error", dir_msg)
            return None

        # Validate URL formats
        invalid = []
        for url in urls:
            ok, msg = downloader.validate_url(url)
            if not ok:
                invalid.append(f"{url} — {msg}")
        if invalid:
            messagebox.showerror("Invalid URL(s)", "\n".join(invalid[:10]))
            return None

        return urls

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        urls = self._validate_inputs()
        if urls is None:
            return

        self._cancel_event.clear()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self.status_var.set("Starting…")
        self._append_log("---")
        self._append_log(f"Starting batch: {len(urls)} URL(s)")

        self._set_running(True)
        self._worker = threading.Thread(
            target=self._run_worker, args=(urls,), daemon=True
        )
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker and self._worker.is_alive():
            self._cancel_event.set()
            self.status_var.set("Cancelling…")
            self._append_log("Cancel requested…")
            self.cancel_btn.configure(state="disabled")

    def _run_worker(self, urls: List[str]) -> None:
        # Snapshot options for thread safety
        output_dir = self.output_var.get().strip()
        quality = self.quality_var.get().strip()
        fmt = self.format_var.get().strip()
        template = self.template_var.get().strip() or "%(title)s.%(ext)s"
        is_playlist = bool(self.playlist_var.get())
        embed_metadata = bool(self.metadata_var.get())
        embed_thumbnail = bool(self.thumbnail_var.get())
        retries = int(self.retries_var.get())
        concurrent = int(self.concurrent_var.get())
        skip_existing = bool(self.skip_existing_var.get())

        use_archive = bool(self.use_archive_var.get())
        archive_file = self.archive_var.get().strip() if use_archive else None

        completed = 0
        total = len(urls)

        def progress_callback(payload: Dict[str, Any]) -> None:
            # payload comes from worker thread
            self._queue.put({"type": "progress", "payload": payload})

        def playlist_progress_callback(
            current: int, total_items: int, title: str
        ) -> None:
            # Playlist-specific progress
            self._queue.put(
                {
                    "type": "playlist_progress",
                    "current": current,
                    "total": total_items,
                    "title": title,
                }
            )

        for idx, url in enumerate(urls, 1):
            if self._cancel_event.is_set():
                self._queue.put({"type": "cancelled"})
                return

            self._queue.put({"type": "status", "text": f"Processing {idx}/{total}"})
            self._queue.put({"type": "log", "text": f"→ {url}"})

            result = downloader.download_audio(
                url=url,
                output_dir=output_dir,
                quality=quality,
                audio_format=fmt,
                embed_metadata=embed_metadata,
                embed_thumbnail=embed_thumbnail,
                filename_template=template,
                quiet=True,
                is_playlist=is_playlist,
                max_retries=retries,
                archive_file=archive_file,
                progress_callback=progress_callback,
                cancel_event=self._cancel_event,
                concurrent_downloads=concurrent,
                skip_existing=skip_existing,
                playlist_progress_callback=playlist_progress_callback,
            )

            completed += 1
            self._queue.put(
                {
                    "type": "result",
                    "result": result,
                    "completed": completed,
                    "total": total,
                }
            )

            if result.error_code == downloader.ErrorCode.CANCELLED:
                self._queue.put({"type": "cancelled"})
                return

        self._queue.put({"type": "done"})

    def _poll_queue(self) -> None:
        """Poll the queue for messages from the worker thread."""
        try:
            while True:
                msg = self._queue.get_nowait()
                self._handle_queue_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)

    def _handle_queue_message(self, msg: Dict[str, Any]) -> None:
        """Handle a single message from the queue."""
        mtype = msg.get("type")

        if mtype == "log":
            self._append_log(str(msg.get("text", "")))

        elif mtype == "status":
            self.status_var.set(str(msg.get("text", "")))

        elif mtype == "progress":
            self._handle_progress(msg.get("payload") or {})

        elif mtype == "playlist_progress":
            self._handle_playlist_progress(msg)

        elif mtype == "result":
            self._handle_result(msg)

        elif mtype == "cancelled":
            self._handle_cancelled()

        elif mtype == "done":
            self._handle_done()

    def _handle_progress(self, payload: Dict[str, Any]) -> None:
        """Handle progress update messages."""
        status = payload.get("status")
        stage = payload.get("stage", "")

        # Handle playlist_progress separately
        if status == "playlist_progress":
            current = payload.get("current", 0)
            total = payload.get("total", 1)
            successful = payload.get("successful", 0)
            skipped = payload.get("skipped", 0)
            failed = payload.get("failed", 0)
            title = payload.get("title", "")

            self.status_var.set(
                f"📋 Playlist: {current}/{total} (✓{successful} ⊘{skipped} ✗{failed})"
            )
            if title:
                self._append_log(f"[{current}/{total}] {title}")

            pct = (current / max(1, total)) * 100.0
            self.progress.configure(mode="determinate")
            self.progress["value"] = pct
            return

        # Update status text based on stage
        stage_messages = {
            "extracting": "⚙ Extracting video information...",
            "downloading": "⬇ Downloading audio stream...",
            "downloaded": "✓ Download complete",
            "converting": f"♪ Converting to audio format...",
            "metadata": "📝 Embedding metadata...",
            "thumbnail": "🖼 Embedding thumbnail...",
        }

        if stage in stage_messages:
            self.status_var.set(stage_messages[stage])

        if status == "downloading":
            total = payload.get("total_bytes")
            downloaded = payload.get("downloaded_bytes")
            if isinstance(total, int) and total > 0 and isinstance(downloaded, int):
                pct = max(0.0, min(100.0, (downloaded / total) * 100.0))
                self.progress.configure(mode="determinate")
                self.progress["value"] = pct
            else:
                # Unknown size
                self.progress.configure(mode="indeterminate")
                self.progress.start(10)

        elif status == "finished":
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.progress["value"] = 100

        elif status == "processing":
            # Post-processing stages (conversion, metadata, thumbnail)
            message = payload.get("message", "Processing...")
            self.progress.configure(mode="indeterminate")
            self.progress.start(10)

        elif status == "error":
            self.progress.stop()

    def _handle_playlist_progress(self, msg: Dict[str, Any]) -> None:
        """Handle playlist-specific progress updates."""
        current = msg.get("current", 0)
        total = msg.get("total", 1)
        title = msg.get("title", "")

        self.status_var.set(f"📋 Playlist: {current}/{total}")
        if title:
            self._append_log(f"  [{current}/{total}] {title}")

        pct = (current / max(1, total)) * 100.0
        self.progress.configure(mode="determinate")
        self.progress["value"] = pct

    def _handle_result(self, msg: Dict[str, Any]) -> None:
        """Handle download result messages."""
        result: downloader.DownloadResult = msg["result"]
        completed = int(msg.get("completed", 0))
        total = int(msg.get("total", 1))

        if result.success:
            self._append_log(f"✓ {result.title or result.url}")
            if result.output_path:
                self._append_log(f"  Saved: {result.output_path}")
        else:
            self._append_log(f"✗ {result.title or result.url}")
            self._append_log(f"  Error: {result.error_message}")

        # coarse overall progress (per-url)
        overall_pct = (completed / max(1, total)) * 100.0
        if self.progress["mode"] != "indeterminate":
            self.progress["value"] = overall_pct
        self.status_var.set(f"Completed {completed}/{total}")

    def _handle_cancelled(self) -> None:
        """Handle cancellation messages."""
        self.progress.stop()
        self.status_var.set("Cancelled")
        self._append_log("Cancelled.")
        self._set_running(False)

    def _handle_done(self) -> None:
        """Handle completion messages."""
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 100
        self.status_var.set("Done")
        self._append_log("All done.")
        self._set_running(False)


def main() -> None:
    root = tk.Tk()

    # Improve default appearance on Windows
    try:
        style = ttk.Style(root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except Exception:
        pass

    App(root)
    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass  # Gracefully handle Ctrl+C


if __name__ == "__main__":
    main()
