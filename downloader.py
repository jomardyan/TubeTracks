#!/usr/bin/env python3
"""TubeTracks: Enhanced YouTube to MP3 Downloader

Download audio from YouTube videos, playlists, and batch files with quality options.
Features: Rich error handling, retries, validation, config file, archive, and detailed reporting.
Plugin system for multi-platform support (YouTube, TikTok, Instagram, Spotify, SoundCloud, etc.).
"""

from __future__ import annotations

import argparse
import io
import json
import locale
import logging
import os
import re
import shutil
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from configparser import ConfigParser, RawConfigParser
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import yt_dlp
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from yt_dlp.utils import DownloadError, ExtractorError, PostProcessingError

# Import plugin system
try:
    from plugins import BaseConverter, ContentType, get_global_registry

    PLUGINS_AVAILABLE = True
except ImportError:
    PLUGINS_AVAILABLE = False

console = Console()

# Version
__version__ = "1.5.1"

# ... rest of downloader.py content remains the same ...