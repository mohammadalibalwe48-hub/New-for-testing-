"""Small helpers shared across the bot."""

from __future__ import annotations

import re
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Literal

URL_RE = re.compile(
    r"https?://[^\s<>\"'`]+",
    re.IGNORECASE,
)

MediaKind = Literal["photo", "video", "audio", "other"]

_PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}
_VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".mov", ".m4v", ".avi", ".flv"}
_AUDIO_EXTS = {".mp3", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".wav", ".flac"}


def extract_first_url(text: str | None) -> str | None:
    """Return the first http(s) URL found in ``text`` or ``None``."""
    if not text:
        return None
    match = URL_RE.search(text)
    return match.group(0) if match else None


def human_size(n_bytes: int) -> str:
    """Format a byte count as a short human-readable string."""
    step = 1024.0
    value = float(n_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < step or unit == "TB":
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= step
    return f"{value:.1f} TB"


def classify_media(path: Path) -> MediaKind:
    """Classify a downloaded file by its extension."""
    ext = path.suffix.lower()
    if ext in _PHOTO_EXTS:
        return "photo"
    if ext in _VIDEO_EXTS:
        return "video"
    if ext in _AUDIO_EXTS:
        return "audio"
    return "other"


@contextmanager
def temp_workspace(base: Path) -> Iterator[Path]:
    """Yield a fresh subdir of ``base``; remove it on exit even on error."""
    base.mkdir(parents=True, exist_ok=True)
    workdir = Path(tempfile.mkdtemp(prefix="dl-", dir=str(base)))
    try:
        yield workdir
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
