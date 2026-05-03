"""Async wrapper around yt-dlp."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .utils import classify_media

log = logging.getLogger(__name__)

MediaKind = Literal["photo", "video", "audio"]


@dataclass
class DownloadResult:
    file_path: Path
    title: str
    source_url: str
    kind: MediaKind


class DownloadError(Exception):
    """Raised on yt-dlp failure, unsupported site, or size > limit after retries."""


def _build_format_selector(*, audio_only: bool, max_height: int, max_filesize: int | None) -> str:
    """Pick a yt-dlp format string that respects our size/quality caps."""
    if audio_only:
        return "bestaudio/best"

    size_clause = f"[filesize<={max_filesize}]" if max_filesize else ""
    height_clause = f"[height<={max_height}]"

    # Prefer mp4-friendly progressive or merged streams; fall back to "best".
    return (
        f"bestvideo{height_clause}{size_clause}[ext=mp4]+bestaudio[ext=m4a]"
        f"/bestvideo{height_clause}{size_clause}+bestaudio"
        f"/best{height_clause}{size_clause}"
        f"/best{height_clause}"
        f"/best"
    )


def _ydl_opts(
    *,
    out_dir: Path,
    audio_only: bool,
    max_height: int,
    max_filesize: int | None,
) -> dict[str, Any]:
    opts: dict[str, Any] = {
        "outtmpl": str(out_dir / "%(title).80s-%(id)s.%(ext)s"),
        "restrictfilenames": True,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "nocheckcertificate": True,
        "retries": 3,
        "fragment_retries": 3,
        "concurrent_fragment_downloads": 4,
        "format": _build_format_selector(
            audio_only=audio_only, max_height=max_height, max_filesize=max_filesize
        ),
    }
    if audio_only:
        opts["postprocessors"] = [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ]
    else:
        # Encourage merged output to be mp4 when ffmpeg has to mux streams.
        opts["merge_output_format"] = "mp4"
    return opts


def _resolve_final_path(info: dict[str, Any], out_dir: Path) -> Path:
    """Find the file yt-dlp actually wrote, tolerating postprocessor renames."""
    requested = info.get("requested_downloads") or []
    for entry in requested:
        path = entry.get("filepath") or entry.get("_filename")
        if path and Path(path).exists():
            return Path(path)

    direct = info.get("filepath") or info.get("_filename")
    if direct and Path(direct).exists():
        return Path(direct)

    # Fallback: pick the largest file in the workspace.
    candidates = [p for p in out_dir.iterdir() if p.is_file()]
    if not candidates:
        raise DownloadError("yt-dlp produced no output file")
    candidates.sort(key=lambda p: p.stat().st_size, reverse=True)
    return candidates[0]


def _kind_from_path(path: Path, *, audio_only: bool) -> MediaKind:
    if audio_only:
        return "audio"
    classified = classify_media(path)
    if classified == "other":
        # Best effort: treat unknowns as videos (Telegram will accept as document).
        return "video"
    return classified  # type: ignore[return-value]


def _download_sync(
    url: str,
    *,
    out_dir: Path,
    audio_only: bool,
    max_height: int,
    max_filesize: int | None,
) -> DownloadResult:
    try:
        from yt_dlp import YoutubeDL  # type: ignore
        from yt_dlp.utils import DownloadError as YDLError  # type: ignore
    except ImportError as exc:  # pragma: no cover - import guard
        raise DownloadError(
            "yt-dlp is not installed. Run `pip install -r bot/requirements.txt`."
        ) from exc

    opts = _ydl_opts(
        out_dir=out_dir,
        audio_only=audio_only,
        max_height=max_height,
        max_filesize=max_filesize,
    )

    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
    except YDLError as exc:
        raise DownloadError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 - surface unexpected failures
        raise DownloadError(f"unexpected downloader error: {exc}") from exc

    if info is None:
        raise DownloadError("downloader returned no metadata")

    # If the URL was a playlist or carousel, take the first entry.
    if "entries" in info and info["entries"]:
        info = info["entries"][0]

    path = _resolve_final_path(info, out_dir)
    title = (info.get("title") or path.stem).strip() or path.stem

    if max_filesize is not None and path.stat().st_size > max_filesize:
        raise DownloadError(
            f"downloaded file is larger than the configured limit "
            f"({path.stat().st_size} bytes > {max_filesize} bytes)"
        )

    return DownloadResult(
        file_path=path,
        title=title,
        source_url=url,
        kind=_kind_from_path(path, audio_only=audio_only),
    )


async def download_media(
    url: str,
    *,
    out_dir: Path,
    audio_only: bool = False,
    max_height: int = 720,
    max_filesize_bytes: int | None = None,
) -> DownloadResult:
    """Run yt-dlp in a thread executor and return a DownloadResult."""
    log.info("downloading %s (audio_only=%s, max_height=%s)", url, audio_only, max_height)
    return await asyncio.to_thread(
        _download_sync,
        url,
        out_dir=out_dir,
        audio_only=audio_only,
        max_height=max_height,
        max_filesize=max_filesize_bytes,
    )
