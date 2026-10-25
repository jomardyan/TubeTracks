"""Tkinter GUI frontend for TubeTracks.

This file intentionally keeps the CLI in downloader.py untouched.
It uses downloader.py as a backend and adds a simple desktop UI.

Run:
  python tubetracks_gui.py
"""

from __future__ import annotations

import argparse
import queue
import sys
import threading
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

import downloader

# ==============================================================================
# TOOLTIP HELPER - Shows helpful hints when hovering over elements
# ==============================================================================


class ToolTip:
    """Simple tooltip that appears when hovering over a widget."""

    def __init__(self, widget: tk.Widget, text: str, delay: int = 500):
        self.widget = widget
        self.text = text
        self.delay = delay
        self.tipwindow: tk.Toplevel | None = None
        self._id: str | None = None
        widget.bind("<Enter>", self._schedule)
        widget.bind("<Leave>", self._hide)
        widget.bind("<ButtonPress>", self._hide)

    def _schedule(self, event=None) -> None:
        self._unschedule()
        self._id = self.widget.after(self.delay, self._show)

    def _unschedule(self) -> None:
        if self._id:
            self.widget.after_cancel(self._id)
            self._id = None

    def _show(self, event=None) -> None:
        if self.tipwindow:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 5
        self.tipwindow = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        # Style the tooltip
        frame = tk.Frame(tw, background="#ffffe0", borderwidth=1, relief="solid")
        frame.pack()
        label = tk.Label(
            frame,
            text=self.text,
            justify="left",
            background="#ffffe0",
            foreground="#333333",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            wraplength=300,
        )
        label.pack()

    def _hide(self, event=None) -> None:
        self._unschedule()
        if self.tipwindow:
            self.tipwindow.destroy()
            self.tipwindow = None


def add_tooltip(widget: tk.Widget, text: str) -> ToolTip:
    """Convenience function to add a tooltip to any widget."""
    return ToolTip(widget, text)


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(f"TubeTracks (GUI) v{downloader.__version__}")
        self.root.minsize(860, 620)

        self._worker: threading.Thread | None = None
        self._cancel_event = threading.Event()
        self._preview_cancel_event = threading.Event()
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._is_running = False
        self._is_previewing = False
        self._pending_logs: list[str] = []
        self._run_errors: list[dict[str, str]] = []
        self._run_cancelled = False
        self._last_playlist_index: int | None = None

        self.root.protocol("WM_DELETE_WINDOW", self._exit_app)
        self._build_menu()
        self._build_ui()
        self._load_config_defaults()
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
        try:
            filename = filedialog.askopenfilename(
                title="Open URLs file",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if not filename:
                return

            try:
                with open(filename, encoding="utf-8") as f:
                    content = f.read()

                # Count valid URLs
                valid_urls = [
                    line.strip()
                    for line in content.splitlines()
                    if line.strip() and not line.strip().startswith("#")
                ]

                self.urls_text.delete("1.0", "end")
                self.urls_text.insert("1.0", content)
                self._append_log(f"✓ Loaded {len(valid_urls)} URL(s) from: {filename}")

            except UnicodeDecodeError:
                # Try with different encoding
                try:
                    with open(filename, encoding="latin-1") as f:
                        content = f.read()
                    self.urls_text.delete("1.0", "end")
                    self.urls_text.insert("1.0", content)
                    self._append_log(
                        f"⚠ Loaded file with alternate encoding: {filename}"
                    )
                except Exception as e:
                    messagebox.showerror(
                        "Encoding Error",
                        f"Cannot decode file:\n\n{filename}\n\nError: {str(e)}",
                    )
                    self._append_log(f"✗ Encoding error: {filename}: {e}")
            except PermissionError:
                messagebox.showerror(
                    "Permission Denied",
                    f"Cannot read file:\n\n{filename}\n\nCheck file permissions.",
                )
                self._append_log(f"✗ Permission denied: {filename}")
            except FileNotFoundError:
                messagebox.showerror(
                    "File Not Found", f"File does not exist:\n\n{filename}"
                )
                self._append_log(f"✗ File not found: {filename}")
            except Exception as e:
                messagebox.showerror(
                    "Error Reading File",
                    f"Failed to read file:\n\n{filename}\n\nError: {str(e)}",
                )
                self._append_log(f"✗ Error reading file: {e}")
        except Exception as e:
            messagebox.showerror(
                "Unexpected Error", f"Error opening file dialog:\n\n{str(e)}"
            )
            self._append_log(f"✗ Unexpected error in file dialog: {e}")

    def _save_log(self) -> None:
        """Save the log to a file."""
        try:
            filename = filedialog.asksaveasfilename(
                title="Save log",
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            )
            if not filename:
                return

            try:
                content = self.log_text.get("1.0", "end")

                # Ensure parent directory exists
                from pathlib import Path

                Path(filename).parent.mkdir(parents=True, exist_ok=True)

                with open(filename, "w", encoding="utf-8") as f:
                    f.write(content)

                messagebox.showinfo("Success", f"Log saved to:\n\n{filename}")
                self._append_log(f"✓ Log saved to: {filename}")

            except PermissionError:
                messagebox.showerror(
                    "Permission Denied",
                    f"Cannot write to file:\n\n{filename}\n\nCheck file/folder permissions.",
                )
                self._append_log(f"✗ Permission denied saving log: {filename}")
            except OSError as e:
                messagebox.showerror(
                    "File Error",
                    f"Failed to save log:\n\n{filename}\n\nError: {str(e)}",
                )
                self._append_log(f"✗ OS error saving log: {e}")
            except Exception as e:
                messagebox.showerror(
                    "Error", f"Failed to save log:\n\n{type(e).__name__}: {str(e)}"
                )
                self._append_log(f"✗ Unexpected error saving log: {e}")
        except Exception as e:
            messagebox.showerror(
                "Unexpected Error", f"Error in save dialog:\n\n{str(e)}"
            )
            self._append_log(f"✗ Unexpected error in save dialog: {e}")

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
            f"TubeTracks (GUI)\n"
            f"Version {downloader.__version__}\n\n"
            f"A multi-platform audio downloader with plugin support.\n"
            f"Supports YouTube, Spotify, SoundCloud, and more.",
        )

    def _exit_app(self) -> None:
        """Cancel background work before closing the window."""
        if self._is_running or self._is_previewing:
            if not messagebox.askyesno(
                "Exit", "An operation is in progress. Exit anyway?"
            ):
                return
        self._cancel_event.set()
        self._preview_cancel_event.set()
        self.root.destroy()

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(6, weight=1)

        # URLs - with user-friendly header
        url_header = ttk.Frame(outer)
        url_header.grid(row=0, column=0, sticky="ew")
        ttk.Label(
            url_header,
            text="Paste video or playlist links here:",
            font=("Segoe UI", 10, "bold"),
        ).pack(side="left")
        ttk.Label(url_header, text="(one link per line)", foreground="gray").pack(
            side="left", padx=(8, 0)
        )

        self.urls_text = tk.Text(outer, height=7, wrap="word")
        self.urls_text.grid(row=1, column=0, sticky="nsew", pady=(6, 10))
        self.urls_text.insert("1.0", "")
        # Placeholder behavior
        self._urls_placeholder = "Example: https://www.youtube.com/watch?v=..."
        self._setup_placeholder(self.urls_text, self._urls_placeholder)
        self._create_context_menu(self.urls_text)

        # Options row
        options = ttk.Frame(outer)
        options.grid(row=2, column=0, sticky="ew")
        for i in range(8):
            options.columnconfigure(i, weight=0)
        options.columnconfigure(1, weight=1)
        options.columnconfigure(6, weight=1)

        ttk.Label(options, text="Save to folder:").grid(row=0, column=0, sticky="w")
        self.output_var = tk.StringVar(value=str(Path.cwd() / "downloads"))
        self.output_entry = ttk.Entry(options, textvariable=self.output_var)
        self.output_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        add_tooltip(self.output_entry, "Where your downloaded files will be saved")
        browse_btn = ttk.Button(options, text="Browse...", command=self._choose_output)
        browse_btn.grid(row=0, column=2, sticky="w")
        add_tooltip(browse_btn, "Click to choose a folder on your computer")

        ttk.Label(options, text="Audio quality:").grid(
            row=0, column=3, sticky="w", padx=(14, 0)
        )
        self.quality_var = tk.StringVar(value="medium")
        # User-friendly quality descriptions
        self._quality_display = {
            "Low (smaller files)": "low",
            "Medium (recommended)": "medium",
            "High (best quality)": "high",
            "Original (lossless)": "best",
        }
        self._quality_reverse = {v: k for k, v in self._quality_display.items()}
        self.quality_combo = ttk.Combobox(
            options,
            values=list(self._quality_display.keys()),
            width=18,
            state="readonly",
        )
        self.quality_combo.set("Medium (recommended)")
        self.quality_combo.bind("<<ComboboxSelected>>", self._on_quality_change)
        self.quality_combo.grid(row=0, column=4, sticky="w", padx=(8, 8))
        add_tooltip(
            self.quality_combo,
            "Higher quality = larger file size. Medium is good for most people.",
        )

        ttk.Label(options, text="File type:").grid(row=0, column=5, sticky="w")
        self.format_var = tk.StringVar(value="mp3")
        # User-friendly format descriptions
        self._format_descriptions = {
            "mp3": "MP3 (works everywhere)",
            "m4a": "M4A (Apple/iTunes)",
            "flac": "FLAC (lossless, large)",
            "wav": "WAV (uncompressed)",
            "ogg": "OGG (open format)",
            "opus": "Opus (efficient)",
            "vorbis": "Vorbis (open)",
            "mp4": "MP4 (video)",
        }
        format_display = [
            self._format_descriptions.get(f, f) for f in downloader.SUPPORTED_FORMATS
        ]
        self.format_combo = ttk.Combobox(
            options,
            values=format_display,
            width=18,
            state="readonly",
        )
        self.format_combo.set("MP3 (works everywhere)")
        self.format_combo.bind("<<ComboboxSelected>>", self._on_format_change)
        self.format_combo.grid(row=0, column=6, sticky="w", padx=(8, 0))
        add_tooltip(
            self.format_combo,
            "MP3 is recommended - it works on all devices and music players.",
        )

        # Secondary options - with user-friendly labels
        options2 = ttk.Frame(outer)
        options2.grid(row=3, column=0, sticky="ew", pady=(10, 10))
        for i in range(14):
            options2.columnconfigure(i, weight=0)
        options2.columnconfigure(11, weight=1)

        self.playlist_var = tk.BooleanVar(value=False)
        playlist_cb = ttk.Checkbutton(
            options2, text="Download entire playlist", variable=self.playlist_var
        )
        playlist_cb.grid(row=0, column=0, sticky="w")
        add_tooltip(
            playlist_cb,
            "Check this if you want to download all videos in a playlist or channel",
        )

        self.metadata_var = tk.BooleanVar(value=True)
        metadata_cb = ttk.Checkbutton(
            options2, text="Add song info", variable=self.metadata_var
        )
        metadata_cb.grid(row=0, column=1, sticky="w", padx=(14, 0))
        add_tooltip(
            metadata_cb,
            "Adds artist name, song title, and album to the file (recommended)",
        )

        self.thumbnail_var = tk.BooleanVar(value=True)
        thumbnail_cb = ttk.Checkbutton(
            options2, text="Add cover art", variable=self.thumbnail_var
        )
        thumbnail_cb.grid(row=0, column=2, sticky="w", padx=(14, 0))
        add_tooltip(
            thumbnail_cb, "Adds the album/video artwork to the audio file (recommended)"
        )

        self.skip_existing_var = tk.BooleanVar(value=True)
        skip_cb = ttk.Checkbutton(
            options2, text="Skip duplicates", variable=self.skip_existing_var
        )
        skip_cb.grid(row=0, column=3, sticky="w", padx=(14, 0))
        add_tooltip(skip_cb, "Don't download files that already exist in the folder")

        concurrent_lbl = ttk.Label(options2, text="Downloads at once:")
        concurrent_lbl.grid(row=0, column=4, sticky="w", padx=(14, 0))
        self.concurrent_var = tk.IntVar(value=3)
        self.concurrent_spin = ttk.Spinbox(
            options2, from_=1, to=5, textvariable=self.concurrent_var, width=5
        )
        self.concurrent_spin.grid(row=0, column=5, sticky="w", padx=(8, 0))
        add_tooltip(
            self.concurrent_spin,
            "How many files to download at the same time. 3 is usually best.",
        )

        retries_lbl = ttk.Label(options2, text="Retry failed:")
        retries_lbl.grid(row=0, column=6, sticky="w", padx=(14, 0))
        self.retries_var = tk.IntVar(value=3)
        self.retries_spin = ttk.Spinbox(
            options2, from_=0, to=20, textvariable=self.retries_var, width=5
        )
        self.retries_spin.grid(row=0, column=7, sticky="w", padx=(8, 0))
        add_tooltip(self.retries_spin, "How many times to retry if a download fails")

        self.use_archive_var = tk.BooleanVar(value=True)
        archive_cb = ttk.Checkbutton(
            options2, text="Remember downloads", variable=self.use_archive_var
        )
        archive_cb.grid(row=0, column=8, sticky="w", padx=(14, 0))
        add_tooltip(
            archive_cb,
            "Keeps a list of downloads so you don't accidentally download the same file twice",
        )
        self.use_archive_var.trace_add("write", self._update_archive_entry_state)

        # Advanced options row (hidden by default for simplicity)
        ttk.Label(options2, text="").grid(
            row=0, column=9, sticky="w", padx=(14, 0)
        )  # spacer

        # Create show/hide advanced link
        self._advanced_visible = tk.BooleanVar(value=False)
        self.advanced_toggle = ttk.Button(
            options2,
            text="Show Advanced Options ▼",
            command=self._toggle_advanced_options,
            width=22,
        )
        self.advanced_toggle.grid(row=0, column=10, sticky="e", padx=(8, 0))
        add_tooltip(
            self.advanced_toggle,
            "Show extra options for power users (proxy, filename template, etc.)",
        )

        # Advanced options frame (starts hidden)
        self.advanced_frame = ttk.LabelFrame(
            outer, text="Advanced Options (for experts)"
        )
        self.advanced_frame.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        self.advanced_frame.grid_remove()  # Hide by default

        for i in range(7):
            self.advanced_frame.columnconfigure(i, weight=1 if i in (1, 4, 6) else 0)

        # Row 0: Archive file and Template
        ttk.Label(self.advanced_frame, text="History file:").grid(
            row=0, column=0, sticky="w", padx=4, pady=4
        )
        self.archive_var = tk.StringVar(value=str(downloader.DEFAULT_ARCHIVE_FILE))
        self.archive_entry = ttk.Entry(
            self.advanced_frame, textvariable=self.archive_var, width=30
        )
        self.archive_entry.grid(row=0, column=1, sticky="ew", padx=(8, 16), pady=4)
        add_tooltip(
            self.archive_entry,
            "File that remembers which videos you've already downloaded",
        )

        ttk.Label(self.advanced_frame, text="Filename pattern:").grid(
            row=0, column=2, sticky="w", padx=4, pady=4
        )
        self.template_var = tk.StringVar(value="%(title)s.%(ext)s")
        self.template_entry = ttk.Entry(
            self.advanced_frame, textvariable=self.template_var, width=25
        )
        self.template_entry.grid(row=0, column=3, sticky="ew", padx=(8, 0), pady=4)
        add_tooltip(
            self.template_entry,
            "How to name the files. %(title)s = video title, %(ext)s = file extension",
        )

        # Row 1: Proxy and Rate limit
        ttk.Label(self.advanced_frame, text="Proxy URL:").grid(
            row=1, column=0, sticky="w", padx=4, pady=4
        )
        self.proxy_var = tk.StringVar()
        self.proxy_entry = ttk.Entry(self.advanced_frame, textvariable=self.proxy_var)
        self.proxy_entry.grid(row=1, column=1, sticky="ew", padx=(8, 16), pady=4)
        add_tooltip(
            self.proxy_entry,
            "Optional: Use a proxy server (e.g., socks5://127.0.0.1:1080)",
        )

        ttk.Label(self.advanced_frame, text="Speed limit:").grid(
            row=1, column=2, sticky="w", padx=4, pady=4
        )
        self.rate_limit_var = tk.StringVar()
        self.rate_limit_entry = ttk.Entry(
            self.advanced_frame, textvariable=self.rate_limit_var, width=12
        )
        self.rate_limit_entry.grid(row=1, column=3, sticky="w", padx=(8, 0), pady=4)
        add_tooltip(
            self.rate_limit_entry,
            "Optional: Limit download speed (e.g., 1M = 1 megabyte/sec)",
        )

        # Row 2: Cookies file
        ttk.Label(self.advanced_frame, text="Cookies file:").grid(
            row=2, column=0, sticky="w", padx=4, pady=4
        )
        self.cookies_var = tk.StringVar()
        self.cookies_entry = ttk.Entry(
            self.advanced_frame, textvariable=self.cookies_var
        )
        self.cookies_entry.grid(
            row=2, column=1, columnspan=2, sticky="ew", padx=(8, 8), pady=4
        )
        add_tooltip(
            self.cookies_entry,
            "Optional: Browser cookies file for private/age-restricted videos",
        )
        self.cookies_button = ttk.Button(
            self.advanced_frame,
            text="Browse...",
            command=self._choose_cookies_file,
            width=10,
        )
        self.cookies_button.grid(row=2, column=3, sticky="w", padx=4, pady=4)

        # Log area with friendly label
        log_header = ttk.Frame(outer)
        log_header.grid(row=5, column=0, sticky="ew")
        ttk.Label(log_header, text="Activity Log", font=("Segoe UI", 9, "bold")).pack(
            side="left"
        )
        ttk.Label(log_header, text="(shows what's happening)", foreground="gray").pack(
            side="left", padx=(8, 0)
        )
        log_frame = ttk.Frame(outer)
        log_frame.grid(row=6, column=0, sticky="nsew", pady=(6, 10))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

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
        bottom.grid(row=7, column=0, sticky="ew")
        bottom.columnconfigure(0, weight=1)

        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(bottom, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )

        self.progress = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        self.progress.grid(row=1, column=0, sticky="ew", pady=(6, 0))

        controls = ttk.Frame(bottom)
        controls.grid(row=0, column=1, rowspan=2, sticky="e", padx=(10, 0))

        self.preview_btn = ttk.Button(
            controls, text="Check URL", command=self._preview, width=12
        )
        self.preview_btn.grid(row=0, column=0, padx=(0, 8))
        add_tooltip(
            self.preview_btn,
            "Check the link and see what will be downloaded before starting",
        )

        self.stop_preview_btn = ttk.Button(
            controls,
            text="Stop Check",
            command=self._stop_preview,
            state="disabled",
            width=10,
        )
        self.stop_preview_btn.grid(row=0, column=1, padx=(0, 8))
        add_tooltip(self.stop_preview_btn, "Stop checking the URL")

        self.plugins_btn = ttk.Button(
            controls, text="Supported Sites", command=self._show_plugins, width=14
        )
        self.plugins_btn.grid(row=0, column=2, padx=(0, 8))
        add_tooltip(
            self.plugins_btn,
            "See which websites are supported (YouTube, Spotify, TikTok, etc.)",
        )

        self.start_btn = ttk.Button(
            controls, text="▶ Download", command=self._start, width=12
        )
        self.start_btn.grid(row=0, column=3, padx=(0, 8))
        add_tooltip(self.start_btn, "Start downloading the audio files")

        self.cancel_btn = ttk.Button(
            controls, text="Stop", command=self._cancel, state="disabled", width=8
        )
        self.cancel_btn.grid(row=0, column=4)
        add_tooltip(self.cancel_btn, "Stop the current download")
        self._update_archive_entry_state()

    def _choose_output(self) -> None:
        """Browse for output directory with validation."""
        try:
            folder = filedialog.askdirectory(title="Choose output folder")
            if not folder:
                return

            try:
                # Validate the folder is accessible
                from pathlib import Path

                test_path = Path(folder)

                if not test_path.exists():
                    create = messagebox.askyesno(
                        "Create Folder",
                        f"Folder does not exist:\n\n{folder}\n\nCreate it now?",
                    )
                    if create:
                        test_path.mkdir(parents=True, exist_ok=True)
                        self.output_var.set(folder)
                        self._append_log(f"✓ Created output folder: {folder}")
                    else:
                        self._append_log("⚠ Folder selection cancelled")
                        return
                else:
                    # Test write permissions
                    test_file = test_path / ".write_test"
                    try:
                        test_file.touch()
                        test_file.unlink()
                    except PermissionError:
                        messagebox.showwarning(
                            "Permission Warning",
                            f"Folder may not be writable:\n\n{folder}\n\nYou may encounter errors during download.",
                        )
                        self._append_log(
                            f"⚠ Warning: folder may not be writable: {folder}"
                        )

                    self.output_var.set(folder)
                    self._append_log(f"✓ Selected output folder: {folder}")

            except PermissionError:
                messagebox.showerror(
                    "Permission Denied",
                    f"Cannot access folder:\n\n{folder}\n\nCheck folder permissions.",
                )
                self._append_log(f"✗ Permission denied: {folder}")
            except Exception as e:
                messagebox.showerror(
                    "Folder Error", f"Cannot use folder:\n\n{folder}\n\nError: {str(e)}"
                )
                self._append_log(f"✗ Error accessing folder: {e}")
        except Exception as e:
            messagebox.showerror(
                "Unexpected Error", f"Error selecting folder:\n\n{str(e)}"
            )
            self._append_log(f"✗ Unexpected error in folder browser: {e}")

    def _choose_cookies_file(self) -> None:
        """Prompt the user to select a cookies file with validation."""
        try:
            filename = filedialog.askopenfilename(
                title="Choose cookies file",
                filetypes=[("Text files", "*.txt *.cookies"), ("All files", "*.*")],
            )
            if not filename:
                return

            try:
                # Validate the file exists and is readable
                from pathlib import Path

                test_path = Path(filename)

                if not test_path.exists():
                    messagebox.showerror(
                        "File Not Found", f"Cookies file does not exist:\n\n{filename}"
                    )
                    self._append_log(f"✗ Cookies file not found: {filename}")
                    return

                # Try to read it to verify permissions
                with open(filename) as f:
                    f.read(1)  # Just read first byte

                self.cookies_var.set(filename)
                self._append_log(f"✓ Selected cookies file: {filename}")

            except PermissionError:
                messagebox.showerror(
                    "Permission Denied",
                    f"Cannot read cookies file:\n\n{filename}\n\nCheck file permissions.",
                )
                self._append_log(f"✗ Permission denied: {filename}")
            except Exception as e:
                messagebox.showwarning(
                    "Cookies File Warning",
                    f"May not be able to read:\n\n{filename}\n\nError: {str(e)}\n\nFile selected anyway.",
                )
                self.cookies_var.set(filename)
                self._append_log(f"⚠ Warning with cookies file {filename}: {e}")
        except Exception as e:
            messagebox.showerror(
                "Unexpected Error", f"Error selecting cookies file:\n\n{str(e)}"
            )
            self._append_log(f"✗ Unexpected error in cookies browser: {e}")

    def _load_config_defaults(self) -> None:
        """Load CLI configuration defaults so GUI stays in sync."""
        config = downloader.load_config()
        self.quality_var.set(config.quality)
        self.format_var.set(config.format)
        if config.output:
            self.output_var.set(config.output)
        if config.template:
            self.template_var.set(config.template)
        self.metadata_var.set(config.embed_metadata)
        self.thumbnail_var.set(config.embed_thumbnail)
        self.retries_var.set(config.retries)
        self.concurrent_var.set(config.concurrent_downloads)
        self.use_archive_var.set(config.use_archive)
        if config.archive_file:
            self.archive_var.set(config.archive_file)
        self.proxy_var.set(config.proxy or "")
        self.rate_limit_var.set(config.rate_limit or "")
        self.cookies_var.set(config.cookies_file or "")

        # Update combo boxes to match loaded values
        if config.quality in self._quality_reverse:
            self.quality_combo.set(self._quality_reverse[config.quality])
        if config.format in self._format_descriptions:
            self.format_combo.set(self._format_descriptions[config.format])

        self._update_archive_entry_state()

    # =========================================================================
    # HELPER METHODS FOR USER-FRIENDLY UI
    # =========================================================================

    def _setup_placeholder(self, widget: tk.Text, placeholder: str) -> None:
        """Setup placeholder text behavior for Text widget."""

        def on_focus_in(event):
            if widget.get("1.0", "end-1c") == placeholder:
                widget.delete("1.0", "end")
                widget.config(foreground="black")

        def on_focus_out(event):
            if not widget.get("1.0", "end-1c").strip():
                widget.delete("1.0", "end")
                widget.insert("1.0", placeholder)
                widget.config(foreground="gray")

        # Initialize with placeholder
        widget.insert("1.0", placeholder)
        widget.config(foreground="gray")
        widget.bind("<FocusIn>", on_focus_in)
        widget.bind("<FocusOut>", on_focus_out)

    def _on_quality_change(self, event=None) -> None:
        """Handle quality combobox selection - map display text to internal value."""
        display_value = self.quality_combo.get()
        actual_value = self._quality_display.get(display_value, "medium")
        self.quality_var.set(actual_value)

    def _on_format_change(self, event=None) -> None:
        """Handle format combobox selection - map display text to internal value."""
        display_value = self.format_combo.get()
        # Find actual format from display text
        for fmt, desc in self._format_descriptions.items():
            if desc == display_value:
                self.format_var.set(fmt)
                return
        # Fallback: if display matches format directly
        if display_value in downloader.SUPPORTED_FORMATS:
            self.format_var.set(display_value)
        else:
            self.format_var.set("mp3")

    def _toggle_advanced_options(self) -> None:
        """Show or hide advanced options panel."""
        if self._advanced_visible.get():
            self.advanced_frame.grid_remove()
            self.advanced_toggle.config(text="Show Advanced Options ▼")
            self._advanced_visible.set(False)
            self._append_log("Advanced options hidden")
        else:
            self.advanced_frame.grid()
            self.advanced_toggle.config(text="Hide Advanced Options ▲")
            self._advanced_visible.set(True)
            self._append_log("Advanced options shown")

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self._trim_log_if_needed()

    def _buffer_log(self, line: str) -> None:
        """Buffer log lines to keep UI responsive during heavy output."""
        self._pending_logs.append(line)

    def _flush_log_buffer(self) -> None:
        if not self._pending_logs:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", "\n".join(self._pending_logs) + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")
        self._pending_logs.clear()
        self._trim_log_if_needed()

    def _trim_log_if_needed(self) -> None:
        """Prevent the log widget from growing unbounded."""
        max_lines = 5000
        trim_lines = 500
        try:
            line_count = int(float(self.log_text.index("end-1c").split(".")[0]))
        except Exception:
            return
        if line_count > max_lines:
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", f"{trim_lines + 1}.0")
            self.log_text.configure(state="disabled")

    def _set_running(self, running: bool) -> None:
        """Enable or disable controls based on running state."""
        self._is_running = running
        state_normal = "normal" if not running else "disabled"
        state_readonly = "readonly" if not running else "disabled"

        self.start_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")
        self.preview_btn.configure(state="disabled" if running else "normal")
        self.urls_text.configure(state=state_normal)
        self.output_entry.configure(state=state_normal)
        self.quality_combo.configure(state=state_readonly)
        self.format_combo.configure(state=state_readonly)
        self.template_entry.configure(state=state_normal)
        self.proxy_entry.configure(state=state_normal)
        self.rate_limit_entry.configure(state=state_normal)
        self.cookies_entry.configure(state=state_normal)
        self.cookies_button.configure(state=state_normal)
        self.retries_spin.configure(state=state_normal)
        self._update_archive_entry_state()

    def _update_archive_entry_state(self, *_args) -> None:
        """Enable/disable archive entry based on checkbox and running state."""
        state = (
            "normal"
            if (not self._is_running and self.use_archive_var.get())
            else "disabled"
        )
        self.archive_entry.configure(state=state)

    def _validate_inputs(self) -> list[str] | None:
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

        cookies_path = self.cookies_var.get().strip()
        if cookies_path and not Path(cookies_path).exists():
            messagebox.showerror("Cookies file not found", cookies_path)
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

    def _collect_options(self) -> dict[str, Any]:
        """Collect current form values for worker thread usage."""
        template = self.template_var.get().strip() or "%(title)s.%(ext)s"

        # Validate and correct retries
        try:
            retries = max(0, int(self.retries_var.get()))
            if retries > 10:
                self._append_log(f"⚠ Warning: Retries capped at 10 (was {retries})")
                retries = 10
        except (tk.TclError, ValueError) as e:
            self._append_log(f"⚠ Invalid retries value, using default (3): {e}")
            retries = 3

        # Validate and correct concurrent downloads
        try:
            concurrent = int(self.concurrent_var.get())
            if concurrent < 1:
                self._append_log("⚠ Concurrent downloads must be >= 1, using 1")
                concurrent = 1
            elif concurrent > 5:
                self._append_log(
                    f"⚠ Concurrent downloads capped at 5 (was {concurrent})"
                )
                concurrent = 5
        except (tk.TclError, ValueError) as e:
            self._append_log(f"⚠ Invalid concurrent value, using default (1): {e}")
            concurrent = 1

        archive_file = None
        if self.use_archive_var.get():
            try:
                archive_file = self.archive_var.get().strip() or str(
                    downloader.DEFAULT_ARCHIVE_FILE
                )
            except Exception as e:
                self._append_log(f"⚠ Archive file error, using default: {e}")
                archive_file = str(downloader.DEFAULT_ARCHIVE_FILE)

        cookies_file = self.cookies_var.get().strip() or None
        proxy = self.proxy_var.get().strip() or None
        rate_limit = self.rate_limit_var.get().strip() or None

        return {
            "output_dir": self.output_var.get().strip(),
            "quality": self.quality_var.get().strip(),
            "audio_format": self.format_var.get().strip(),
            "template": template,
            "is_playlist": bool(self.playlist_var.get()),
            "embed_metadata": bool(self.metadata_var.get()),
            "embed_thumbnail": bool(self.thumbnail_var.get()),
            "retries": retries,
            "concurrent_downloads": concurrent,
            "skip_existing": bool(self.skip_existing_var.get()),
            "archive_file": archive_file,
            "proxy": proxy,
            "rate_limit": rate_limit,
            "cookies_file": cookies_file,
        }

    def _preview(self) -> None:
        """Show a dry-run preview for the first URL (runs in background thread)."""
        if self._is_running or self._is_previewing:
            return

        urls = self._validate_inputs()
        if not urls:
            return

        # Set preview state
        self._is_previewing = True
        self._preview_cancel_event.clear()

        # Disable preview/start buttons, enable stop button
        self.preview_btn.configure(state="disabled")
        self.start_btn.configure(state="disabled")
        self.stop_preview_btn.configure(state="normal")

        # Set up progress indication
        self.progress.configure(mode="indeterminate")
        self.progress.start(10)
        self.status_var.set("🔍 Fetching preview...")

        options = self._collect_options()
        url = urls[0]

        # Run preview in background thread
        preview_thread = threading.Thread(
            target=self._preview_worker, args=(url, options), daemon=True
        )
        preview_thread.start()

    def _preview_worker(self, url: str, options: dict[str, Any]) -> None:
        """Background worker for preview operation."""
        try:
            self._queue.put({"type": "log", "text": f"🔍 Fetching preview for: {url}"})
            self._queue.put({"type": "status", "text": "🔍 Connecting to platform..."})

            # Check if cancelled before starting
            if self._preview_cancel_event.is_set():
                self._queue.put({"type": "log", "text": "⊘ Preview cancelled by user"})
                return

            # Extract info with progress updates
            info = self._fetch_preview_with_progress(
                url=url,
                output_dir=options["output_dir"],
                filename_template=options["template"],
                audio_format=options["audio_format"],
                quality=options["quality"],
                is_playlist=options["is_playlist"],
                proxy=options["proxy"],
                cookies_file=options["cookies_file"],
                rate_limit=options["rate_limit"],
            )

            if self._preview_cancel_event.is_set():
                self._queue.put({"type": "log", "text": "⊘ Preview cancelled by user"})
                return

            if not info:
                if self._preview_cancel_event.is_set():
                    self._queue.put(
                        {"type": "log", "text": "⊘ Preview cancelled by user"}
                    )
                    return
                self._queue.put(
                    {
                        "type": "preview_error",
                        "title": "Preview Failed",
                        "message": "Unable to extract information from URL.\n\nPossible causes:\n"
                        "• Invalid or unsupported URL\n"
                        "• Network connectivity issues\n"
                        "• Content is private or restricted\n"
                        "• Platform changes or updates needed",
                    }
                )
                self._queue.put(
                    {"type": "log", "text": "✗ Preview failed – unable to extract info"}
                )
                return

            # Send preview data to main thread
            self._queue.put({"type": "preview_ready", "url": url, "info": info})

        except downloader.DownloadError as e:
            if self._preview_cancel_event.is_set():
                self._queue.put({"type": "log", "text": "⊘ Preview cancelled by user"})
                return
            self._queue.put(
                {
                    "type": "preview_error",
                    "title": "Download Error",
                    "message": f"Failed to fetch preview:\n\n{str(e)}",
                }
            )
            self._queue.put({"type": "log", "text": f"✗ Preview error: {e}"})
        except ConnectionError as e:
            if self._preview_cancel_event.is_set():
                self._queue.put({"type": "log", "text": "⊘ Preview cancelled by user"})
                return
            self._queue.put(
                {
                    "type": "preview_error",
                    "title": "Network Error",
                    "message": f"Connection failed while fetching preview:\n\n{str(e)}\n\n"
                    "Please check your internet connection.",
                }
            )
            self._queue.put({"type": "log", "text": f"✗ Network error: {e}"})
        except Exception as e:
            if self._preview_cancel_event.is_set():
                self._queue.put({"type": "log", "text": "⊘ Preview cancelled by user"})
                return
            self._queue.put(
                {
                    "type": "preview_error",
                    "title": "Unexpected Error",
                    "message": f"An unexpected error occurred:\n\n{type(e).__name__}: {str(e)}\n\n"
                    "Please check the log for details.",
                }
            )
            self._queue.put(
                {
                    "type": "log",
                    "text": f"✗ Unexpected preview error: {type(e).__name__}: {e}",
                }
            )
            import traceback

            self._queue.put(
                {"type": "log", "text": f"Traceback: {traceback.format_exc()}"}
            )
        finally:
            # Always restore UI state
            self._queue.put({"type": "preview_complete"})

    def _fetch_preview_with_progress(
        self,
        url: str,
        output_dir: str,
        filename_template: str,
        audio_format: str,
        quality: str,
        is_playlist: bool,
        **kwargs,
    ) -> dict[str, Any] | None:
        """Fetch preview info with progress updates."""
        try:
            # Check if cancelled
            if self._preview_cancel_event.is_set():
                return None

            self._queue.put({"type": "log", "text": "  → Extracting metadata..."})
            self._queue.put({"type": "status", "text": "🔍 Extracting metadata..."})

            info = downloader.dry_run_info(
                url=url,
                output_dir=output_dir,
                filename_template=filename_template,
                audio_format=audio_format,
                quality=quality,
                is_playlist=is_playlist,
                **kwargs,
            )

            # Check if cancelled after extraction
            if self._preview_cancel_event.is_set():
                return None

            if info:
                video_count = info.get("video_count", 0)
                is_playlist_result = info.get("is_playlist", False)

                if is_playlist_result:
                    self._queue.put(
                        {
                            "type": "log",
                            "text": f"  ✓ Found playlist with {video_count} videos",
                        }
                    )
                    self._queue.put(
                        {"type": "status", "text": f"✓ Playlist: {video_count} videos"}
                    )

                    # Log each video as we process it
                    videos = info.get("videos", [])
                    for idx, video in enumerate(videos[:10], 1):
                        # Check if cancelled during video processing
                        if self._preview_cancel_event.is_set():
                            self._queue.put(
                                {"type": "log", "text": "  ⊘ Preview cancelled"}
                            )
                            return None
                        title = video.get("title", "Unknown")
                        self._queue.put({"type": "log", "text": f"    [{idx}] {title}"})

                    if video_count > 10:
                        self._queue.put(
                            {
                                "type": "log",
                                "text": f"    ... and {video_count - 10} more videos",
                            }
                        )
                else:
                    title = (
                        info.get("videos", [{}])[0].get("title", "Unknown")
                        if info.get("videos")
                        else "Unknown"
                    )
                    self._queue.put(
                        {"type": "log", "text": f"  ✓ Found video: {title}"}
                    )
                    self._queue.put({"type": "status", "text": "✓ Preview ready"})

                self._queue.put(
                    {
                        "type": "log",
                        "text": f"  → Format: {audio_format} @ {quality} quality",
                    }
                )

            return info

        except Exception as e:
            self._queue.put(
                {"type": "log", "text": f"  ✗ Error during preview fetch: {e}"}
            )
            raise

    def _display_preview_info(self, url: str, info: dict[str, Any]) -> None:
        """Render preview data in a dialog."""
        videos = info.get("videos", [])
        total = info.get("video_count", len(videos))
        preview_rows = []

        header = []
        if info.get("playlist_title"):
            header.append(f"Playlist: {info['playlist_title']}")
        header.append(f"Videos: {total}")
        header.append(f"Format: {info.get('format')}")
        header.append(f"Output: {info.get('output_dir')}")
        preview_rows.extend(header)
        preview_rows.append("")

        for idx, video in enumerate(videos[:5], 1):
            duration = video.get("duration")
            if isinstance(duration, (int, float)):
                minutes = int(duration) // 60
                seconds = int(duration) % 60
                duration_str = f"{minutes}:{seconds:02d}"
            else:
                duration_str = "N/A"
            preview_rows.append(
                f"{idx}. {video.get('title', 'Unknown')} ({duration_str})\n   → {video.get('resolved_path')}"
            )

        remaining = max(0, len(videos) - 5)
        if remaining:
            preview_rows.append(f"...and {remaining} more item(s)")

        messagebox.showinfo("Dry Run Preview", "\n".join(preview_rows))
        self._append_log(f"Preview ready for {url}")

    def _show_plugins(self) -> None:
        """Display supported plugin platforms."""
        try:
            platforms = downloader.list_supported_platforms()
            if not platforms:
                messagebox.showwarning(
                    "No Plugins",
                    "No plugins are currently available.\n\n"
                    "This might indicate a configuration issue.",
                )
                self._append_log("⚠ Warning: No plugins available")
                return

            lines = []
            for plugin_id, data in sorted(platforms.items()):
                try:
                    playlist = "✓" if data.get("supports_playlist") else "✗"
                    formats = ", ".join(data.get("output_formats", [])[:3]) or "N/A"
                    platform_name = data.get("platform", plugin_id)
                    lines.append(
                        f"{platform_name} — Formats: {formats} — Playlist: {playlist}"
                    )
                except Exception as e:
                    self._append_log(f"⚠ Error formatting plugin {plugin_id}: {e}")
                    continue

            if not lines:
                messagebox.showerror(
                    "Plugin Error",
                    "Failed to format plugin information.\n\nCheck the log for details.",
                )
                return

            messagebox.showinfo(
                "Supported Platforms", "\n".join(lines) + f"\n\nTotal: {len(platforms)}"
            )
            self._append_log(f"✓ Displayed {len(platforms)} supported plugins")
        except Exception as e:
            messagebox.showerror(
                "Plugin Error", f"Failed to retrieve plugin information:\n\n{str(e)}"
            )
            self._append_log(f"✗ Error loading plugins: {e}")

    def _start(self) -> None:
        if self._worker and self._worker.is_alive():
            return

        urls = self._validate_inputs()
        if urls is None:
            return

        options = self._collect_options()
        self._cancel_event.clear()
        self._run_errors.clear()
        self._run_cancelled = False
        self.progress.configure(mode="determinate")
        self.progress["value"] = 0
        self.status_var.set("Starting…")
        self._append_log("---")
        self._append_log(f"Starting batch: {len(urls)} URL(s)")

        self._set_running(True)
        self._worker = threading.Thread(
            target=self._run_worker, args=(urls, options), daemon=True
        )
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker and self._worker.is_alive():
            self._cancel_event.set()
            self.status_var.set("Cancelling…")
            self._append_log("Cancel requested…")
            self.cancel_btn.configure(state="disabled")

    def _stop_preview(self) -> None:
        """Stop the running preview operation."""
        if self._is_previewing:
            self._preview_cancel_event.set()
            self.status_var.set("Stopping preview…")
            self._append_log("⊘ Preview stop requested…")
            self.stop_preview_btn.configure(state="disabled")

    def _run_worker(self, urls: list[str], options: dict[str, Any]) -> None:
        """Worker thread for processing downloads with comprehensive error handling."""
        try:
            # Snapshot options for thread safety
            output_dir = options["output_dir"]
            quality = options["quality"]
            fmt = options["audio_format"]
            template = options["template"]
            is_playlist = options["is_playlist"]
            embed_metadata = options["embed_metadata"]
            embed_thumbnail = options["embed_thumbnail"]
            retries = options["retries"]
            concurrent = options["concurrent_downloads"]
            skip_existing = options["skip_existing"]
            archive_file = options["archive_file"]
            proxy = options["proxy"]
            rate_limit = options["rate_limit"]
            cookies_file = options["cookies_file"]

            completed = 0
            total = len(urls)
        except KeyError as e:
            self._queue.put(
                {"type": "log", "text": f"✗ Configuration error: Missing option {e}"}
            )
            self._queue.put({"type": "error", "message": f"Configuration error: {e}"})
            return
        except Exception as e:
            self._queue.put(
                {"type": "log", "text": f"✗ Worker initialization error: {e}"}
            )
            self._queue.put({"type": "error", "message": f"Initialization failed: {e}"})
            return

        def progress_callback(payload: dict[str, Any]) -> None:
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

        def download_one(idx: int, url: str) -> downloader.DownloadResult:
            if self._cancel_event.is_set():
                return downloader.DownloadResult(
                    success=False,
                    url=url,
                    error_code=downloader.ErrorCode.CANCELLED,
                    error_message="Download cancelled by user",
                    attempts=0,
                )

            try:
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
                    proxy=proxy,
                    rate_limit=rate_limit,
                    cookies_file=cookies_file,
                    progress_callback=progress_callback,
                    cancel_event=self._cancel_event,
                    skip_existing=skip_existing,
                    playlist_progress_callback=playlist_progress_callback,
                )
            except PermissionError as e:
                result = downloader.DownloadResult(
                    success=False,
                    url=url,
                    error_code=downloader.ErrorCode.PERMISSION_ERROR,
                    error_message=f"Permission denied: {str(e)}",
                )
                self._queue.put(
                    {"type": "log", "text": f"✗ Permission error for {url}: {e}"}
                )
            except ConnectionError as e:
                result = downloader.DownloadResult(
                    success=False,
                    url=url,
                    error_code=downloader.ErrorCode.NETWORK_ERROR,
                    error_message=f"Network error: {str(e)}",
                )
                self._queue.put(
                    {"type": "log", "text": f"✗ Network error for {url}: {e}"}
                )
            except TimeoutError as e:
                result = downloader.DownloadResult(
                    success=False,
                    url=url,
                    error_code=downloader.ErrorCode.TIMEOUT_ERROR,
                    error_message=f"Download timed out: {str(e)}",
                )
                self._queue.put({"type": "log", "text": f"✗ Timeout for {url}: {e}"})
            except Exception as e:
                result = downloader.DownloadResult(
                    success=False,
                    url=url,
                    error_code=downloader.ErrorCode.UNKNOWN_ERROR,
                    error_message=f"Unexpected error: {type(e).__name__}: {str(e)}",
                )
                self._queue.put(
                    {
                        "type": "log",
                        "text": f"✗ Unexpected error for {url}: {type(e).__name__}: {e}",
                    }
                )
                import traceback

                self._queue.put(
                    {"type": "log", "text": f"Traceback: {traceback.format_exc()}"}
                )

            return result

        cancelled = False
        with ThreadPoolExecutor(max_workers=concurrent) as executor:
            futures = [
                executor.submit(download_one, idx, url)
                for idx, url in enumerate(urls, 1)
            ]
            for future in as_completed(futures):
                result = future.result()
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
                    cancelled = True
                    self._cancel_event.set()

        self._queue.put(
            {
                "type": "cancelled"
                if cancelled or self._cancel_event.is_set()
                else "done"
            }
        )

    def _poll_queue(self) -> None:
        """Poll the queue for messages from the worker thread."""
        try:
            processed = 0
            max_messages = 50
            while processed < max_messages:
                msg = self._queue.get_nowait()
                self._handle_queue_message(msg)
                processed += 1
        except queue.Empty:
            pass
        except Exception as e:
            # Critical: queue polling failed
            self._append_log(f"✗ Queue polling error: {type(e).__name__}: {e}")
            import traceback

            self._append_log(f"Traceback: {traceback.format_exc()}")
        finally:
            self._flush_log_buffer()
            # Always reschedule polling to keep GUI responsive
            try:
                self.root.after(100, self._poll_queue)
            except Exception:
                # Even scheduling failed - this is very bad
                pass

    def _handle_queue_message(self, msg: dict[str, Any]) -> None:
        """Handle a single message from the queue."""
        try:
            mtype = msg.get("type")

            if mtype == "log":
                self._buffer_log(str(msg.get("text", "")))

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

            elif mtype == "error":
                # Critical worker error
                error_msg = msg.get("message", "Unknown error")
                self._append_log(f"✗ Critical error: {error_msg}")
                self.status_var.set(f"Error: {error_msg}")
                self._set_running(False)
                messagebox.showerror(
                    "Download Error",
                    f"A critical error occurred:\n\n{error_msg}\n\n"
                    "Check the log for more details.",
                )

            elif mtype == "preview_ready":
                # Preview data is ready - display it
                self._display_preview_info(msg.get("url", ""), msg.get("info", {}))

            elif mtype == "preview_error":
                # Preview operation failed - show error
                messagebox.showerror(
                    msg.get("title", "Error"), msg.get("message", "Unknown error")
                )

            elif mtype == "preview_complete":
                # Preview operation finished - restore UI
                self._is_previewing = False
                self.progress.stop()
                self.progress.configure(mode="determinate")
                self.progress["value"] = 0
                self.status_var.set("Idle")
                self.preview_btn.configure(state="normal")
                self.start_btn.configure(state="normal")
                self.stop_preview_btn.configure(state="disabled")

        except Exception as e:
            # Failsafe: if message handling itself fails
            self._append_log(f"✗ Error handling queue message: {type(e).__name__}: {e}")
            import traceback

            self._append_log(f"Traceback: {traceback.format_exc()}")

    def _handle_progress(self, payload: dict[str, Any]) -> None:
        """Handle progress update messages."""
        status = payload.get("status")
        stage = payload.get("stage", "")
        info_dict = payload.get("info_dict") or {}
        playlist_index = payload.get("playlist_index") or info_dict.get(
            "playlist_index"
        )
        playlist_count = payload.get("playlist_count") or info_dict.get(
            "playlist_count"
        )
        title = info_dict.get("title") or payload.get("filename") or ""

        if playlist_index and playlist_count:
            label = (
                f"[{playlist_index}/{playlist_count}] {title}"
                if title
                else f"[{playlist_index}/{playlist_count}]"
            )

            percent_str = payload.get("_percent_str")
            speed_str = payload.get("_speed_str")
            eta = payload.get("eta")
            eta_str = ""
            if isinstance(eta, (int, float)) and eta > 0:
                eta_str = f" ETA {int(eta)}s"

            if status == "downloading":
                if playlist_index != self._last_playlist_index:
                    self._buffer_log(f"▶ {label}")
                    self._last_playlist_index = int(playlist_index)
                if percent_str or speed_str:
                    status_line = f"{label}"
                    if percent_str:
                        status_line += f" {percent_str}"
                    if speed_str:
                        status_line += f" at {speed_str}"
                    status_line += eta_str
                    self.status_var.set(status_line)
            elif status == "finished":
                self._buffer_log(f"✓ {label} done")
            elif status == "processing" and stage:
                self.status_var.set(f"{label} – {stage}")

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
            "converting": "♪ Converting to audio format...",
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
            payload.get("message", "Processing...")
            self.progress.configure(mode="indeterminate")
            self.progress.start(10)

        elif status == "error":
            self.progress.stop()

    def _handle_playlist_progress(self, msg: dict[str, Any]) -> None:
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

    def _handle_result(self, msg: dict[str, Any]) -> None:
        """Handle download result messages."""
        try:
            result: downloader.DownloadResult = msg["result"]
            completed = int(msg.get("completed", 0))
        except (KeyError, ValueError, TypeError) as e:
            self._append_log(f"✗ Error parsing result message: {e}")
            return
        total = int(msg.get("total", 1))

        if result.success:
            if result.skipped:
                self._append_log(f"⊘ {result.title or result.url}")
                self._append_log(f"  {result.error_message}")
            else:
                self._append_log(f"✓ {result.title or result.url}")
                if result.output_path:
                    self._append_log(f"  Saved: {result.output_path}")
        else:
            self._append_log(f"✗ {result.title or result.url}")
            self._append_log(f"  Error: {result.error_message}")
            self._run_errors.append(
                {"url": result.url or "Unknown URL", "error": result.error_message}
            )

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
        self._run_cancelled = True
        self._set_running(False)

    def _handle_done(self) -> None:
        """Handle completion messages."""
        self.progress.stop()
        self.progress.configure(mode="determinate")
        self.progress["value"] = 100
        self.status_var.set("Done")
        self._append_log("All done.")
        self._set_running(False)
        self._last_playlist_index = None
        if self._run_errors and not self._run_cancelled:
            preview = []
            for err in self._run_errors[:3]:
                preview.append(f"{err['url']}\n  {err['error']}")
            extra = ""
            if len(self._run_errors) > 3:
                extra = f"\n\n...and {len(self._run_errors) - 3} more error(s)."
            messagebox.showwarning(
                "Some downloads failed",
                f"{len(self._run_errors)} URL(s) failed.\n\n"
                + "\n\n".join(preview)
                + extra,
            )


def main() -> None:
    # Parse arguments before initializing GUI (for --help, --version in headless environments)
    parser = argparse.ArgumentParser(
        description="TubeTracks - Tkinter GUI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"tubetracks-gui {downloader.__version__}",
    )

    # Check for help/version before tkinter initialization (fixes CI/headless issues)
    if "--help" in sys.argv or "-h" in sys.argv or "--version" in sys.argv:
        parser.parse_args()
        return

    # Parse remaining args (currently none, but ready for future expansion)
    parser.parse_args()

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
