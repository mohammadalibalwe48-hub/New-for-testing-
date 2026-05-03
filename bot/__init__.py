"""Telegram bot for downloading videos and photos via yt-dlp."""

__all__ = ["main"]


def main() -> None:  # pragma: no cover - thin re-export
    """Lazy re-export so importing submodules doesn't pull in telegram/ytdlp."""
    from .main import main as _main

    _main()
